"""Upstox V3 HTTP client for historical and intraday candle data.

V3 URL format:
  Historical: GET /v3/historical-candle/{instrument_key}/{unit}/{interval}/{to_date}/{from_date}
  Intraday:   GET /v3/historical-candle/intraday/{instrument_key}/{unit}/{interval}

Where:
  {unit}     = minutes | hours | days | weeks | months
  {interval} = positive integer (1, 3, 5, 15, 30, etc.)
  dates      = YYYY-MM-DD

Authentication: Bearer token required (UPSTOX_ACCESS_TOKEN env var)
"""

import asyncio
import logging
import time
from datetime import date, timedelta
from typing import Any, AsyncGenerator

import httpx

from .feed import UpstoxFeed
from .models import Candle, is_intraday_unit, tv_resolution_to_upstox, upstox_chunk_days
from terminal.symbols.service import get_symbol
from .provider import CandleProvider

logger = logging.getLogger(__name__)

BASE_URL = "https://api.upstox.com/v3"

# Retry config
MAX_RETRIES = 5
RETRY_BACKOFF = 0.5  # seconds, doubled each retry

# Candle cache TTL — results are reused for this many seconds before re-fetching.
# Short enough to stay fresh during a session; long enough to serve N simultaneous
# chart widgets that all open at the same time without duplicating API calls.
CANDLE_CACHE_TTL = 60.0  # seconds

# Exchange prefixes that belong to Indian markets
INDIA_EXCHANGES = {"NSE", "BSE"}


class UpstoxClient(CandleProvider):
    """Upstox V3 candle provider for Indian markets (NSE, BSE).

    Implements :class:`CandleProvider` for the ``"india"`` market.
    Provides methods for fetching historical and intraday OHLCV candles.
    Manages a shared ``httpx.AsyncClient`` for connection pooling.
    """

    @property
    def market(self) -> str:
        return "india"

    def get_candle_feed_token(self, ticker: str) -> str | None:
        """Convert ``NSE:RELIANCE`` to ``NSE_EQ|INE002A01018`` or ``NSE_INDEX|Nifty 50``."""
        sym = get_symbol(ticker)
        if not sym:
            return None

        exchange = ticker.split(":")[0] if ":" in ticker else "NSE"
        # Normalize exchange (e.g. NSE_EQ -> NSE, BSE_INDEX -> BSE)
        base_exchange = exchange.split("_")[0]

        # Handle Indices
        if sym.get("type") == "index":
            return f"{base_exchange}_INDEX|{sym['name']}"

        # Handle Stocks
        if sym.get("isin"):
            return f"{base_exchange}_EQ|{sym['isin']}"

        return None

    def __init__(
        self,
        access_token: str | None = None,
        timeout: float = 30.0,
        feed: UpstoxFeed | None = None,
        owns_feed: bool = True,
    ) -> None:
        self._access_token = access_token
        self._client: httpx.AsyncClient | None = None
        self._timeout = timeout
        self._feed = feed
        self._owns_feed = owns_feed
        self._update_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._ticker_map: dict[str, str] = {}  # token -> ticker

        # Candle cache: cache_key -> (candles, expires_monotonic)
        # Keyed on raw (ticker, interval, from_date, to_date) before date expansion so
        # two simultaneous "full range" requests share the same entry.
        self._candle_cache: dict[str, tuple[list[Candle], float]] = {}
        # In-flight dedup: cache_key -> Future
        # Second caller awaits the same future instead of starting a new fetch.
        self._candle_inflight: dict[str, asyncio.Future[list[Candle]]] = {}

        if self._feed:
            self._feed.on_candle(self._on_feed_update)

    async def subscribe(self, ticker: str) -> None:
        token = self.get_candle_feed_token(ticker)
        if not token:
            return
        # Always record in ticker_map so attach_feed() can replay pending subs
        self._ticker_map[token] = ticker
        if self._feed:
            await self._feed.subscribe([token])

    async def unsubscribe(self, ticker: str) -> None:
        token = self.get_candle_feed_token(ticker)
        if not token:
            return
        self._ticker_map.pop(token, None)
        if self._feed:
            await self._feed.unsubscribe([token])

    async def attach_feed(self, feed: UpstoxFeed) -> None:
        """Attach a shared feed to this client.

        Registers the candle callback and replays any subscriptions that
        were requested before the feed was available.
        """
        if self._feed is feed:
            return
        if self._feed:
            self._feed.remove_callback(self._on_feed_update)
        self._feed = feed
        feed.on_candle(self._on_feed_update)
        # Replay pending subscriptions
        if self._ticker_map:
            await feed.subscribe(list(self._ticker_map.keys()))

    async def on_update(self) -> AsyncGenerator[dict[str, Any], None]:
        """Yields real-time updates for subscribed tickers."""
        while True:
            update = await self._update_queue.get()
            yield update

    async def _on_feed_update(self, token: str, ohlc: dict[str, Any]) -> None:
        ticker = self._ticker_map.get(token)
        if ticker:
            self._update_queue.put_nowait({"ticker": ticker, **ohlc})

    async def start_feed(self) -> None:
        if self._feed:
            await self._feed.start()

    async def stop_feed(self) -> None:
        if self._feed and self._owns_feed:
            await self._feed.stop()

    @property
    def has_feed(self) -> bool:
        return self._feed is not None

    @property
    def is_feed_connected(self) -> bool:
        return self._feed is not None and self._feed.is_connected

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
            if self._access_token:
                headers["Authorization"] = f"Bearer {self._access_token}"

            self._client = httpx.AsyncClient(
                base_url=BASE_URL,
                timeout=self._timeout,
                headers=headers,
                limits=httpx.Limits(
                    # Each chart session fetches N chunks in parallel.
                    # 50 connections comfortably serves ~5 simultaneous chart widgets.
                    max_connections=50,
                    max_keepalive_connections=20,
                ),
            )
        return self._client

    async def close(self) -> None:
        """Deregister from the feed and close the HTTP client.

        If this client owns its feed (``owns_feed=True``), the feed is also
        stopped. When using a shared feed from the registry, the registry
        controls the feed lifecycle — we only deregister our callback.
        """
        if self._feed:
            self._feed.remove_callback(self._on_feed_update)
            if self._owns_feed:
                await self._feed.stop()

        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def get_candles(
        self,
        ticker: str,
        interval: str,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> list[Candle]:
        """Fetch candles with TTL cache + in-flight deduplication.

        Multiple simultaneous requests for the same (ticker, interval, from, to)
        are collapsed into one Upstox API call — subsequent callers await the
        same Future rather than firing redundant HTTP requests.  Results are then
        cached for CANDLE_CACHE_TTL seconds so back-to-back chart opens are instant.
        """
        cache_key = f"{ticker}:{interval}:{from_date}:{to_date}"
        now = time.monotonic()

        # ── 1. Cache hit ──────────────────────────────────────────────────
        entry = self._candle_cache.get(cache_key)
        if entry is not None:
            candles, expires_at = entry
            if now < expires_at:
                logger.debug("Candle cache hit for %s %s", ticker, interval)
                return candles
            del self._candle_cache[cache_key]

        # ── 2. In-flight dedup ────────────────────────────────────────────
        # If another coroutine is already fetching the same key, wait for it.
        inflight = self._candle_inflight.get(cache_key)
        if inflight is not None:
            logger.debug("Waiting for in-flight candle fetch for %s %s", ticker, interval)
            return await asyncio.shield(inflight)

        # ── 3. New fetch — register Future so late arrivals can piggyback ─
        loop = asyncio.get_event_loop()
        fut: asyncio.Future[list[Candle]] = loop.create_future()
        self._candle_inflight[cache_key] = fut
        try:
            candles = await self._do_get_candles(ticker, interval, from_date, to_date)
            self._candle_cache[cache_key] = (candles, time.monotonic() + CANDLE_CACHE_TTL)
            fut.set_result(candles)
            return candles
        except Exception as exc:
            if not fut.done():
                fut.set_exception(exc)
            raise
        finally:
            self._candle_inflight.pop(cache_key, None)

    async def _do_get_candles(
        self,
        ticker: str,
        interval: str,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> list[Candle]:
        """Internal implementation — always hits the Upstox API.

        Args:
            ticker:    e.g. ``NSE:RELIANCE``
            interval:  TradingView resolution string OR internal format.
                       e.g. "1", "5", "60", "1D", "1W", "1M" (TV format)
                       or  "1m", "5m", "1h", "1d", "1w"  (internal format)
            from_date: Start of the requested window (inclusive).
            to_date:   End of the requested window (inclusive). Defaults to today.

        Returns:
            List of candles in chronological order (oldest first).
            Returns [] when no data is available (caller should signal noData).
        """
        token = self.get_candle_feed_token(ticker)
        if not token:
            logger.error("Could not resolve candle token for ticker: %s", ticker)
            return []

        # Map interval → Upstox (unit, num)
        upstox = tv_resolution_to_upstox(interval)
        if upstox is None:
            logger.error("Cannot map interval %r to Upstox format", interval)
            return []
        unit, num = upstox

        import urllib.parse

        encoded_token = urllib.parse.quote(token)

        today = date.today()
        effective_to = to_date if to_date is not None else today
        # Never request data beyond today
        effective_to = min(effective_to, today)

        # Enforce minimum data windows for better "scroll back" performance.
        # For intraday intervals we use the chunk size (7 days) as the minimum
        # so each request results in exactly one Upstox API call, avoiding
        # the 4–5 parallel requests that previously caused rate-limit retries
        # and frontend timeouts on intervals like 15m.
        chunk_days = upstox_chunk_days(unit)
        if from_date is None:
            if unit in ("days", "weeks", "months"):
                # 5 years back for daily+
                from_date = effective_to - timedelta(days=1825)
            else:
                # One chunk back for intraday (7 days)
                from_date = effective_to - timedelta(days=chunk_days)
        else:
            # Expand the window up to the minimum if the caller requested less.
            if unit in ("days", "weeks", "months"):
                min_from = effective_to - timedelta(days=1825)
                from_date = min(from_date, min_from)
            else:
                min_from = effective_to - timedelta(days=chunk_days)
                from_date = min(from_date, min_from)

        # ── 1 & 2. Historical + intraday candles fired in parallel ────────
        # Intraday only applies to sub-daily intervals when the window includes today.
        need_intraday = is_intraday_unit(unit) and effective_to >= today

        async def _fetch_intraday() -> list[Candle]:
            intra_path = (
                f"/historical-candle/intraday/{encoded_token}/{unit}/{num}"
            )
            candles = await self._fetch_candles(intra_path)
            if candles:
                logger.debug(
                    "Intraday candles fetched for %s: %d bars",
                    ticker,
                    len(candles),
                )
            return candles

        historical_coro = self._fetch_all_historical(
            encoded_token, unit, num, from_date, effective_to
        )
        intraday_coro = _fetch_intraday() if need_intraday else asyncio.sleep(0)

        hist_result, intra_result = await asyncio.gather(
            historical_coro, intraday_coro
        )
        historical_candles: list[Candle] = hist_result or []
        intraday_candles: list[Candle] = intra_result if need_intraday else []

        # ── 3. Merge & deduplicate ─────────────────────────────────────────
        # We use a dict to let intraday candles overwrite historical ones for the same timestamp,
        # ensuring the most "live" data is preserved.
        merged_dict: dict[str, Candle] = {}
        for candle_list in [historical_candles, intraday_candles]:
            for c in candle_list:
                merged_dict[c.timestamp] = c

        merged = sorted(merged_dict.values(), key=lambda x: x.timestamp)
        logger.info(
            "get_candles for %s %s: total %d bars (hist: %d, intra: %d)",
            ticker,
            interval,
            len(merged),
            len(historical_candles),
            len(intraday_candles),
        )
        return merged

    async def _fetch_all_historical(
        self,
        encoded_token: str,
        unit: str,
        num: str,
        from_date: date,
        to_date: date,
    ) -> list[Candle]:
        """Fetch historical data in parallel chunks."""
        chunk_days = upstox_chunk_days(unit)

        # Calculate all required chunks upfront
        chunks = []
        current_to = to_date
        while current_to >= from_date:
            current_from = max(from_date, current_to - timedelta(days=chunk_days - 1))
            chunks.append((current_from, current_to))
            current_to = current_from - timedelta(days=1)

        if not chunks:
            return []

        logger.info(
            "Fetching %d historical chunks for %s %s/%s from %s to %s",
            len(chunks),
            encoded_token,
            unit,
            num,
            from_date,
            to_date,
        )

        # Create tasks for parallel fetching
        tasks = []
        for c_from, c_to in chunks:
            path = (
                f"/historical-candle/{encoded_token}/{unit}/{num}"
                f"/{c_to.isoformat()}/{c_from.isoformat()}"
            )
            tasks.append(self._fetch_candles(path))

        # Run in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_candles: list[Candle] = []
        for i, res in enumerate(results):
            if isinstance(res, Exception):
                logger.error("Chunk fetch failed: %s", res)
                continue
            if res:
                all_candles.extend(res)
            else:
                c_from, c_to = chunks[i]
                logger.debug("Chunk %s to %s returned no data", c_from, c_to)

        # Final deduplication and sorting
        merged_dict: dict[str, Candle] = {}
        for c in all_candles:
            merged_dict[c.timestamp] = c

        return sorted(merged_dict.values(), key=lambda x: x.timestamp)

    async def _fetch_candles(self, path: str) -> list[Candle]:
        """Execute the HTTP request with retry logic and parse candle data."""
        client = await self._ensure_client()
        last_exc: Exception | None = None

        for attempt in range(MAX_RETRIES):
            try:
                response = await client.get(path)

                if response.status_code == 429:
                    # Rate limited — backoff and retry
                    wait = RETRY_BACKOFF * (2**attempt)
                    logger.warning(
                        "Rate limited by Upstox, retrying in %.1fs (attempt %d/%d)",
                        wait,
                        attempt + 1,
                        MAX_RETRIES,
                    )
                    await asyncio.sleep(wait)
                    continue

                response.raise_for_status()
                data = response.json()

                if data.get("status") != "success":
                    logger.error("Upstox API error for %s: %s", path, data)
                    return []

                raw_candles = data.get("data", {}).get("candles", [])
                return self._parse_candles(raw_candles)

            except httpx.HTTPStatusError as exc:
                logger.error(
                    "Upstox HTTP error %d for %s: %s",
                    exc.response.status_code,
                    path,
                    exc.response.text,
                )
                last_exc = exc
                break  # Don't retry on non-429 HTTP errors

            except (httpx.ConnectError, httpx.ReadTimeout) as exc:
                last_exc = exc
                wait = RETRY_BACKOFF * (2**attempt)
                logger.warning(
                    "Connection error for %s, retrying in %.1fs (attempt %d/%d): %s",
                    path,
                    wait,
                    attempt + 1,
                    MAX_RETRIES,
                    exc,
                )
                await asyncio.sleep(wait)

        if last_exc:
            logger.error(
                "Failed to fetch candles from %s after %d attempts", path, MAX_RETRIES
            )
        return []

    @staticmethod
    def _parse_candles(raw_candles: list[list]) -> list[Candle]:
        """Parse Upstox candle arrays into Candle objects.

        Upstox format: [timestamp, open, high, low, close, volume, oi]
        Response is newest-first — we reverse to return oldest-first (chronological).

        Timestamps from Upstox are IST ISO strings like "2025-01-02T09:15:00+05:30".
        We keep them as-is in the Candle model, but we'll convert to UTC ms in chart.py.
        """
        candles = []
        for row in raw_candles:
            if len(row) < 7:
                continue

            timestamp = str(row[0])
            candles.append(
                Candle(
                    timestamp=timestamp,
                    open=float(row[1]),
                    high=float(row[2]),
                    low=float(row[3]),
                    close=float(row[4]),
                    volume=int(row[5]),
                    oi=int(row[6]),
                )
            )

        # Upstox returns newest first — reverse for chronological order
        candles.reverse()
        return candles
