"""Upstox V3 WebSocket market data feed for real-time candle updates.

Connects to the Upstox market data feed WebSocket, subscribes to instruments
in ``full`` mode, and broadcasts OHLC updates via an async callback interface.

The feed sends protobuf-encoded ``FeedResponse`` messages. This module
decodes them using the compiled proto stubs in ``proto/MarketDataFeed_pb2``.
"""

import asyncio
import json
import logging
import uuid
from typing import Any, Callable, Awaitable

import httpx
import websockets
from websockets.asyncio.client import ClientConnection

from .proto import MarketDataFeed_pb2 as pb
from .models import tv_resolution_to_upstox

logger = logging.getLogger(__name__)

AUTHORIZE_URL = "https://api.upstox.com/v3/feed/market-data-feed/authorize"

# Reconnect config
INITIAL_RECONNECT_DELAY = 1.0
MAX_RECONNECT_DELAY = 60.0
RECONNECT_BACKOFF_FACTOR = 2.0


CandleCallback = Callable[[str, dict[str, Any]], Awaitable[None]]
"""Callback signature: async def callback(instrument_key, ohlc_data)"""


class UpstoxFeed:
    """WebSocket client for Upstox V3 Market Data Feed.

    Manages a single WebSocket connection with:
    - Automatic authorization via REST endpoint
    - Subscription management (subscribe/unsubscribe instruments)
    - Auto-reconnect with exponential backoff
    - Protobuf decoding of binary feed messages
    - Callback-based OHLC update delivery
    """

    def __init__(self, access_token: str) -> None:
        self._access_token = access_token
        self._ws: ClientConnection | None = None
        self._subscribed_keys: set[str] = set()
        self._callbacks: list[CandleCallback] = []
        self._run_task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()
        self._reconnect_delay = INITIAL_RECONNECT_DELAY

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the WebSocket connection in a background task."""
        if self._run_task and not self._run_task.done():
            logger.warning("UpstoxFeed is already running.")
            return

        self._stop_event.clear()
        self._reconnect_delay = INITIAL_RECONNECT_DELAY
        self._run_task = asyncio.create_task(self._connection_loop())
        logger.info("UpstoxFeed started.")

    async def stop(self) -> None:
        """Stop the WebSocket connection and background task."""
        self._stop_event.set()
        if self._ws:
            await self._ws.close()
            self._ws = None
        if self._run_task:
            self._run_task.cancel()
            try:
                await self._run_task
            except asyncio.CancelledError:
                pass
            self._run_task = None
        logger.info("UpstoxFeed stopped.")

    # ------------------------------------------------------------------
    # Subscription management
    # ------------------------------------------------------------------

    async def subscribe(self, instrument_keys: list[str]) -> None:
        """Subscribe to instruments for real-time OHLC data (full mode)."""
        new_keys = [k for k in instrument_keys if k not in self._subscribed_keys]
        if not new_keys:
            return

        self._subscribed_keys.update(new_keys)

        if self._ws:
            await self._send_subscription("sub", new_keys)

    async def unsubscribe(self, instrument_keys: list[str]) -> None:
        """Unsubscribe from instruments."""
        keys_to_remove = [k for k in instrument_keys if k in self._subscribed_keys]
        if not keys_to_remove:
            return

        self._subscribed_keys -= set(keys_to_remove)

        if self._ws:
            await self._send_subscription("unsub", keys_to_remove)

    def on_candle(self, callback: CandleCallback) -> None:
        """Register a callback for OHLC updates.

        Callback receives ``(instrument_key, ohlc_dict)`` where ``ohlc_dict``
        has keys: ``interval``, ``open``, ``high``, ``low``, ``close``, ``volume``, ``ts``.
        """
        self._callbacks.append(callback)

    # ------------------------------------------------------------------
    # Internal — connection management
    # ------------------------------------------------------------------

    async def _get_authorized_url(self) -> str | None:
        """Call the authorize endpoint to get the WebSocket URL."""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(
                    AUTHORIZE_URL,
                    headers={
                        "Authorization": f"Bearer {self._access_token}",
                        "Accept": "application/json",
                    },
                )
                response.raise_for_status()
                data = response.json()

                if data.get("status") == "success":
                    return data["data"]["authorized_redirect_uri"]

                logger.error("Authorization failed: %s", data)
                return None

        except Exception as exc:
            logger.error("Failed to get authorized feed URL: %s", exc)
            return None

    async def _connection_loop(self) -> None:
        """Main connection loop with auto-reconnect."""
        while not self._stop_event.is_set():
            try:
                ws_url = await self._get_authorized_url()
                if not ws_url:
                    logger.error(
                        "Could not authorize WebSocket. Retrying in %.1fs",
                        self._reconnect_delay,
                    )
                    await self._wait_or_stop(self._reconnect_delay)
                    self._reconnect_delay = min(
                        self._reconnect_delay * RECONNECT_BACKOFF_FACTOR,
                        MAX_RECONNECT_DELAY,
                    )
                    continue

                logger.info("Connecting to Upstox feed: %s", ws_url[:80])
                async with websockets.connect(ws_url) as ws:
                    self._ws = ws
                    self._reconnect_delay = INITIAL_RECONNECT_DELAY
                    logger.info("Connected to Upstox market data feed.")

                    # Re-subscribe to any existing subscriptions
                    if self._subscribed_keys:
                        await self._send_subscription(
                            "sub", list(self._subscribed_keys)
                        )

                    await self._receive_loop(ws)

            except websockets.ConnectionClosed as exc:
                logger.warning("WebSocket closed: %s. Reconnecting...", exc)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error(
                    "Unexpected feed error: %s. Reconnecting in %.1fs",
                    exc,
                    self._reconnect_delay,
                )

            self._ws = None

            if not self._stop_event.is_set():
                await self._wait_or_stop(self._reconnect_delay)
                self._reconnect_delay = min(
                    self._reconnect_delay * RECONNECT_BACKOFF_FACTOR,
                    MAX_RECONNECT_DELAY,
                )

    async def _receive_loop(self, ws: ClientConnection) -> None:
        """Read protobuf binary messages from the WebSocket and dispatch them."""
        async for raw_message in ws:
            if self._stop_event.is_set():
                break

            try:
                # Upstox sends binary protobuf messages
                if not isinstance(raw_message, bytes):
                    raw_message = raw_message.encode("utf-8")

                feed_response = pb.FeedResponse()
                feed_response.ParseFromString(raw_message)

                if feed_response.type == pb.market_info:
                    logger.info("Received market info update.")
                elif feed_response.type in (pb.live_feed, pb.initial_feed):
                    await self._handle_feed_response(feed_response)

            except Exception as exc:
                logger.error("Error processing feed message: %s", exc, exc_info=True)

    async def _handle_feed_response(self, feed_response: pb.FeedResponse) -> None:
        """Extract OHLC data from a decoded FeedResponse and invoke callbacks."""
        if not feed_response.feeds:
            return

        for instrument_key, feed in feed_response.feeds.items():
            if instrument_key not in self._subscribed_keys:
                logger.debug(
                    "Received update for unsubscribed key %s. Subscribed: %s",
                    instrument_key,
                    list(self._subscribed_keys),
                )
                continue

            ohlc_list = self._extract_ohlc(feed)
            if ohlc_list:
                logger.debug(
                    "Extracted %d candles for %s", len(ohlc_list), instrument_key
                )
            else:
                logger.warning(
                    "Empty OHLC list extracted for key %s (full_feed: %s)",
                    instrument_key,
                    feed.HasField("fullFeed"),
                )

            for ohlc in ohlc_list:
                for callback in self._callbacks:
                    try:
                        await callback(instrument_key, ohlc)
                    except Exception as exc:
                        logger.error(
                            "Error in candle callback for %s: %s",
                            instrument_key,
                            exc,
                        )

    @staticmethod
    def _extract_ohlc(feed: pb.Feed) -> list[dict[str, Any]]:
        """Extract OHLC candles from a protobuf Feed message.

        Supports:
        - fullFeed → marketFF → marketOHLC → ohlc[]
        - fullFeed → indexFF → marketOHLC → ohlc[]
        """
        results = []

        if not feed.HasField("fullFeed"):
            return results

        full_feed = feed.fullFeed

        # Get marketOHLC from either marketFF or indexFF
        market_ohlc = None
        if full_feed.HasField("marketFF"):
            market_ohlc = full_feed.marketFF.marketOHLC
        elif full_feed.HasField("indexFF"):
            market_ohlc = full_feed.indexFF.marketOHLC

        if market_ohlc is None:
            return results

        for ohlc in market_ohlc.ohlc:
            # ohlc.interval is a raw string from the feed (e.g. '1d', '1minute', '1week')
            # Convert to (unit, num) via the same parser the rest of the stack uses
            upstox_parts = tv_resolution_to_upstox(ohlc.interval)
            if upstox_parts is None:
                # Fallback: try stripping common suffixes
                raw = ohlc.interval.lower()
                if raw in ("1d", "day"):
                    upstox_parts = ("days", "1")
                elif raw in ("1w", "week"):
                    upstox_parts = ("weeks", "1")
                elif raw in ("1month", "month", "1M"):
                    upstox_parts = ("months", "1")
                else:
                    upstox_parts = ("minutes", "1")  # safe default

            unit, num = upstox_parts
            # TV resolution string to emit with the update (normalize to our internal format)
            if unit == "days":
                iv_str = f"{num}d"
            elif unit == "weeks":
                iv_str = f"{num}w"
            elif unit == "months":
                iv_str = f"{num}M"
            elif unit == "hours":
                iv_str = f"{num}h"
            else:
                iv_str = f"{num}m"

            # Binary feed sends timestamps in milliseconds (true UTC epoch from Upstox)
            ts_ms = ohlc.ts

            results.append(
                {
                    "interval": iv_str,
                    "open": ohlc.open,
                    "high": ohlc.high,
                    "low": ohlc.low,
                    "close": ohlc.close,
                    "volume": ohlc.vol,
                    "timestamp": ts_ms,
                }
            )

        return results

    async def _send_subscription(self, method: str, instrument_keys: list[str]) -> None:
        """Send a subscribe/unsubscribe message over the WebSocket.

        Subscription messages are sent as JSON-encoded binary.
        """
        if not self._ws:
            return

        message = {
            "guid": uuid.uuid4().hex[:20],
            "method": method,
            "data": {
                "mode": "full",
                "instrumentKeys": instrument_keys,
            },
        }

        try:
            await self._ws.send(json.dumps(message).encode("utf-8"))
            logger.info(
                "Sent %s for %d instruments: %s",
                method,
                len(instrument_keys),
                instrument_keys[:5],
            )
        except Exception as exc:
            logger.error("Failed to send %s message: %s", method, exc)

    async def _wait_or_stop(self, delay: float) -> None:
        """Wait for the given delay or until stop is signalled."""
        try:
            await asyncio.wait_for(self._stop_event.wait(), timeout=delay)
        except asyncio.TimeoutError:
            pass

    @property
    def is_connected(self) -> bool:
        """Whether the WebSocket is currently connected."""
        return self._ws is not None
