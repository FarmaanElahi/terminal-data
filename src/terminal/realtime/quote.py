"""QuoteSession — per-quote subscription state within a RealtimeSession."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Set, Optional

if TYPE_CHECKING:
    from .session import RealtimeSession
    from terminal.market_feed.manager import MarketDataManager

from .models import (
    QuoteRequest,
    FullQuoteResponse,
    QuoteUpdateResponse,
    QuoteData,
    QuoteUpdateData,
)

logger = logging.getLogger(__name__)


class QuoteSession:
    """
    Holds state for a single quote subscription session.

    Created via ``create_quote_session`` and stored inside the
    parent :class:`RealtimeSession`. Manages a background task that
    listens to MarketDataManager updates and forwards them to the client.
    """

    def __init__(
        self,
        session_id: str,
        *,
        realtime: "RealtimeSession",
        manager: "MarketDataManager",
    ) -> None:
        self.session_id = session_id
        self.realtime = realtime
        self.manager = manager
        self.subscribed_symbols: Set[str] = set()
        self._last_emitted: dict[str, dict] = {}
        self._streaming_task: Optional[asyncio.Task] = None

    def _candle_to_dict(self, candle: tuple) -> dict:
        return {
            "timestamp": int(candle[0]),
            "open": float(candle[1]),
            "high": float(candle[2]),
            "low": float(candle[3]),
            "close": float(candle[4]),
            "volume": float(candle[5]),
        }

    async def handle(self, msg: QuoteRequest) -> None:
        """Handle a quote request forwarded from the RealtimeSession."""
        match msg.m:
            case "create_quote_session":
                await self._handle_subscribe(msg.p[1])
            case "subscribe_symbols":
                await self._handle_subscribe(msg.p[1])
            case "unsubscribe_symbols":
                await self._handle_unsubscribe(msg.p[1])
            case _:
                logger.warning("Unhandled quote message: %s", msg.m)

    async def _handle_subscribe(self, symbols: list[str]) -> None:
        """Add symbols to the subscription and send initial data."""
        new_symbols = []
        for symbol in symbols:
            if symbol not in self.subscribed_symbols:
                self.subscribed_symbols.add(symbol)
                new_symbols.append(symbol)

        if not new_symbols:
            return

        # 1. Send latest data for these new symbols immediately (First emit)
        for symbol in new_symbols:
            latest = self.manager.get_ohlcv_series(symbol, limit=1)
            if latest:
                candle_dict = self._candle_to_dict(latest[0])
                self._last_emitted[symbol] = candle_dict
                await self.realtime.send(
                    FullQuoteResponse(
                        p=(self.session_id, symbol, QuoteData(**candle_dict)),
                    )
                )

        # 2. Ensure streaming task is running
        if self._streaming_task is None or self._streaming_task.done():
            self._streaming_task = asyncio.create_task(self._stream_loop())

    async def _handle_unsubscribe(self, symbols: list[str]) -> None:
        """Remove symbols from the subscription."""
        for symbol in symbols:
            self.subscribed_symbols.discard(symbol)

    async def _stream_loop(self) -> None:
        """Background loop listening to MarketDataManager for updates."""
        try:
            async for update in self.manager.subscribe():
                symbol = update["symbol"]
                if symbol in self.subscribed_symbols:
                    candle_dict = self._candle_to_dict(update["candle"])

                    if symbol not in self._last_emitted:
                        self._last_emitted[symbol] = candle_dict
                        await self.realtime.send(
                            FullQuoteResponse(
                                p=(self.session_id, symbol, QuoteData(**candle_dict)),
                            )
                        )
                    else:
                        last_dict = self._last_emitted[symbol]
                        diff = {}
                        for k, v in candle_dict.items():
                            if last_dict.get(k) != v:
                                diff[k] = v

                        if diff:
                            self._last_emitted[symbol] = candle_dict
                            await self.realtime.send(
                                QuoteUpdateResponse(
                                    p=(
                                        self.session_id,
                                        symbol,
                                        QuoteUpdateData(**diff),
                                    ),
                                )
                            )
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error in QuoteSession {self.session_id} stream loop: {e}")

    def stop(self) -> None:
        """Stop the streaming task."""
        if self._streaming_task:
            self._streaming_task.cancel()
            self._streaming_task = None

    def __repr__(self) -> str:
        return f"QuoteSession(id={self.session_id!r}, symbols={len(self.subscribed_symbols)})"
