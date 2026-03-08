import asyncio
import logging
import time
from typing import AsyncGenerator

import pandas as pd

from .store import OHLCStore
from .provider import PartitionedProvider, _extract_exchange, EXCHANGES
from terminal.infra.circuit_breaker import CircuitBreaker, CircuitOpenError

logger = logging.getLogger(__name__)


class BroadcastChannel:
    """Lock-free broadcast using asyncio.Condition.

    Publishers call ``publish()`` to update the latest state.
    Subscribers call ``subscribe()`` to get an async generator of updates.
    No per-subscriber queues — zero-copy, instant wakeup.
    """

    def __init__(self) -> None:
        self._latest: dict[str, tuple] = {}
        self._version: int = 0
        self._condition: asyncio.Condition = asyncio.Condition()

    async def publish(self, symbol: str, candle: tuple) -> None:
        self._latest[symbol] = candle
        self._version += 1
        async with self._condition:
            self._condition.notify_all()

    async def subscribe(self) -> AsyncGenerator[dict, None]:
        """Yield ``{"symbol": ..., "candle": ...}`` dicts on each publish."""
        last_version = self._version
        while True:
            async with self._condition:
                await self._condition.wait_for(lambda: self._version > last_version)
                current_version = self._version
            for sym, candle in list(self._latest.items()):
                yield {"symbol": sym, "candle": candle}
            last_version = current_version


class MarketDataManager:
    """Coordinates data loading and realtime updates between OHLCStore and PartitionedProvider.

    Uses TradingView websocket quote stream when available,
    with Scanner API polling as a fallback.
    Includes circuit breaker for external API resilience and staleness tracking.

    All exchange data is lazy-loaded on first symbol access.
    """

    def __init__(
        self,
        store: OHLCStore,
        provider: PartitionedProvider,
        poll_interval: float = 5.0,
        refresh_interval: float = 3600.0,  # 1 hour background data refresh
    ):
        self.store = store
        self.provider = provider
        self.poll_interval = poll_interval
        self.refresh_interval = refresh_interval
        self._streaming_task: asyncio.Task | None = None
        self._refresh_task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()
        self._broadcast = BroadcastChannel()

        # Circuit breaker for scanner API
        self._circuit = CircuitBreaker(
            "scanner",
            failure_threshold=5,
            recovery_timeout=30.0,
            half_open_max_calls=1,
        )

        # Staleness tracking
        self._last_successful_poll: float | None = None
        self._consecutive_failures: int = 0

    @property
    def staleness_seconds(self) -> float | None:
        """Seconds since last successful poll, or None if never polled."""
        if self._last_successful_poll is None:
            return None
        return time.time() - self._last_successful_poll

    @property
    def is_data_stale(self) -> bool:
        """True if no successful poll in the last 60 seconds."""
        staleness = self.staleness_seconds
        return staleness is not None and staleness > 60

    async def start(self):
        """Starts realtime streaming.

        Exchange data is NOT eagerly loaded — it will be lazy-loaded
        on first symbol access via ``get_ohlcv()`` or ``ensure_symbol_loaded()``.
        """
        try:
            logger.info("Starting MarketDataManager (lazy loading mode)...")

            # Discover tickers from already-loaded exchanges (may be empty at first)
            tickers = self.provider.get_all_tickers("1D")

            if tickers:
                logger.info("Found %d pre-loaded symbols, starting streaming.", len(tickers))
                await self.start_realtime_streaming(tickers)
            else:
                logger.info(
                    "No symbols pre-loaded (lazy mode). "
                    "Streaming will start when exchanges are loaded."
                )

            # Start the background data refresh loop
            self._refresh_task = asyncio.create_task(self._data_refresh_loop())
            logger.info(
                "Background data refresh started (interval=%ds)",
                int(self.refresh_interval),
            )
        except Exception as e:
            logger.error("Failed to start MarketDataManager: %s", e, exc_info=True)

    async def ensure_symbol_loaded(self, symbol: str, timeframe: str = "1D") -> None:
        """Ensure the exchange data for a symbol is loaded, lazy-loading if needed."""
        exchange = _extract_exchange(symbol)
        await self.provider.ensure_loaded(timeframe, exchange)

        # Load from provider into store if not already there
        if not self.store.has_symbol(symbol, timeframe):
            history = self.provider.get_history(symbol, timeframe)
            if history is not None and len(history) > 0:
                self.store.load_history(symbol, history, timeframe)

    async def load_history(self, symbols: list[str], timeframe: str = "1D"):
        """Loads historical data for a list of symbols into the store.

        Ensures the required exchanges are loaded first.
        """
        logger.info("Loading history for %d symbols...", len(symbols))

        # Determine which exchanges need loading
        exchanges_needed = {_extract_exchange(s) for s in symbols}
        await asyncio.gather(
            *[self.provider.ensure_loaded(timeframe, ex) for ex in exchanges_needed]
        )

        for symbol in symbols:
            try:
                history = self.provider.get_history(symbol, timeframe)
                if history is not None and len(history) > 0:
                    self.store.load_history(symbol, history, timeframe)
            except Exception as e:
                logger.error("Failed to load history for %s: %s", symbol, e)

    async def ensure_streaming(self) -> None:
        """Start streaming if exchanges have been loaded but streaming wasn't started.

        This handles the lazy-loading case: ``start()`` finds no tickers
        and skips streaming.  When the screener (or any other consumer)
        later loads exchanges, it should call this to kick off the stream.
        """
        if self._streaming_task and not self._streaming_task.done():
            return  # already running

        tickers = self.provider.get_all_tickers("1D")
        if tickers:
            logger.info(
                "Deferred streaming start: %d tickers now available.",
                len(tickers),
            )
            await self.start_realtime_streaming(tickers)

    async def start_realtime_streaming(self, tickers: list[str]):
        """Starts the background realtime task for OHLCV updates."""
        if self._streaming_task and not self._streaming_task.done():
            logger.warning("Realtime streaming is already running.")
            return

        self._stop_event.clear()
        if getattr(self.provider, "supports_live_stream", False):
            self._streaming_task = asyncio.create_task(self._stream_quote_loop(tickers))
        else:
            self._streaming_task = asyncio.create_task(self._stream_loop(tickers))
        logger.info("Started realtime streaming for %d tickers", len(tickers))

    async def stop_realtime_streaming(self):
        """Stops the background streaming task."""
        self._stop_event.set()
        # Wake up any subscribers blocked on the broadcast condition
        async with self._broadcast._condition:
            self._broadcast._condition.notify_all()
        if self._streaming_task:
            self._streaming_task.cancel()
            try:
                await self._streaming_task
            except asyncio.CancelledError:
                pass
            self._streaming_task = None
        if self._refresh_task:
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                pass
            self._refresh_task = None
        logger.info("Stopped realtime streaming.")

    # ------------------------------------------------------------------
    # Background data refresh
    # ------------------------------------------------------------------

    async def _data_refresh_loop(self) -> None:
        """Periodically check ETags for all loaded exchanges and reload when changed.

        This runs in the background so screener sessions never trigger
        a remote sync themselves — they just use whatever data is in memory.
        """
        try:
            while not self._stop_event.is_set():
                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(), timeout=self.refresh_interval
                    )
                    break  # stop event was set
                except asyncio.TimeoutError:
                    pass  # interval elapsed, time to refresh

                # Check all loaded exchange keys
                loaded_keys = list(self.provider._data.keys())
                if not loaded_keys:
                    continue

                reloaded = 0
                for tf, exchange in loaded_keys:
                    try:
                        changed = await asyncio.to_thread(
                            self.provider._check_and_sync, tf, exchange
                        )
                        if changed:
                            await asyncio.to_thread(
                                self.provider._load_exchange, tf, exchange
                            )
                            # Reload symbols into the store
                            symbols = self.provider._data.get((tf, exchange), {})
                            for symbol, history in symbols.items():
                                if history is not None and len(history) > 0:
                                    self.store.load_history(symbol, history, tf)
                            reloaded += 1
                    except Exception as e:
                        logger.warning(
                            "Background refresh failed for %s/%s: %s",
                            tf, exchange, e,
                        )

                if reloaded:
                    logger.info(
                        "Background refresh: reloaded %d/%d exchange files",
                        reloaded, len(loaded_keys),
                    )
                    # Restart streaming with new tickers if needed
                    await self.ensure_streaming()
                else:
                    logger.debug(
                        "Background refresh: all %d exchange files up-to-date",
                        len(loaded_keys),
                    )

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error("Background data refresh loop crashed: %s", e, exc_info=True)

    async def _stream_loop(self, tickers: list[str]):
        """Polling loop that fetches daily OHLCV from TradingView Scanner API every interval.

        Updates the store and broadcasts changes. Uses circuit breaker for resilience.
        """
        ticker_set = set(tickers)
        try:
            while not self._stop_event.is_set():
                try:
                    ohlcv_data = await self._circuit.call(
                        self.provider.fetch_live_ohlcv
                    )

                    for ticker, candle in ohlcv_data.items():
                        if ticker not in ticker_set:
                            continue

                        self.store.add_realtime(ticker, candle)
                        await self._broadcast.publish(ticker, candle)

                    # Track success
                    self._last_successful_poll = time.time()
                    self._consecutive_failures = 0

                except CircuitOpenError:
                    staleness = self.staleness_seconds
                    logger.warning(
                        "Circuit breaker OPEN — serving cached data (stale %.0fs)",
                        staleness or 0,
                    )

                except Exception as e:
                    self._consecutive_failures += 1
                    logger.error(
                        "Error fetching scanner OHLCV (failures=%d): %s",
                        self._consecutive_failures,
                        e,
                        exc_info=True,
                    )

                    if self._consecutive_failures >= 12:  # ~60s at 5s intervals
                        logger.warning(
                            "Data stale: %d consecutive poll failures",
                            self._consecutive_failures,
                        )

                # Poll every 5 seconds
                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(), timeout=self.poll_interval
                    )
                    break
                except asyncio.TimeoutError:
                    pass

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error("Error in realtime stream loop: %s", e, exc_info=True)

    async def _stream_quote_loop(self, tickers: list[str]):
        """Streaming loop that subscribes to TradingView quote updates.

        Updates the store and broadcasts changes.
        """
        ticker_set = set(tickers)
        stream_callable = getattr(self.provider, "stream_live_ohlcv", None)
        if stream_callable is None or not callable(stream_callable):
            logger.info("Live stream unavailable, falling back to polling.")
            await self._stream_loop(tickers)
            return

        while not self._stop_event.is_set():
            try:
                async for symbol, candle in stream_callable(tickers):
                    if self._stop_event.is_set():
                        break
                    if symbol not in ticker_set:
                        continue

                    self.store.add_realtime(symbol, candle)
                    await self._broadcast.publish(symbol, candle)

                    self._last_successful_poll = time.time()
                    self._consecutive_failures = 0

            except asyncio.CancelledError:
                raise
            except Exception as e:
                self._consecutive_failures += 1
                logger.error(
                    "Error in quote stream loop (failures=%d): %s",
                    self._consecutive_failures,
                    e,
                    exc_info=True,
                )

                if self._consecutive_failures >= 5:
                    logger.warning(
                        "Quote stream unstable, switching to polling fallback."
                    )
                    await self._stream_loop(tickers)
                    return

                if self._stop_event.is_set():
                    break

                # Reconnect delay before retrying the quote stream.
                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(), timeout=self.poll_interval
                    )
                    break
                except asyncio.TimeoutError:
                    continue

            else:
                if self._stop_event.is_set():
                    break

                # If stream closes normally (rare), retry after interval.
                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(), timeout=self.poll_interval
                    )
                    break
                except asyncio.TimeoutError:
                    continue

    async def subscribe(self) -> AsyncGenerator[dict, None]:
        """Allows modules to subscribe to real-time bar updates via broadcast channel.

        Yields {"symbol": ..., "candle": ...} dicts.
        """
        async for update in self._broadcast.subscribe():
            if self._stop_event.is_set():
                break
            yield update

    def get_data(self, symbol: str, timeframe: str = "1D"):
        """Convenience method to get data from the underlying store."""
        return self.store.get_data(symbol, timeframe)

    def get_ohlcv(self, symbol: str, timeframe: str = "D") -> pd.DataFrame | None:
        """Returns OHLCV data as a pandas DataFrame.

        Resamples the data if a higher timeframe (W, M, Y) is requested.
        Lazy-loads from provider if symbol is not yet in the store.
        """
        # Map short timeframe codes to provider timeframes
        store_tf = "1D"  # base timeframe for resampling
        df = self.store.get_data(symbol, store_tf)

        # Lazy loading: if not in store, try loading from provider
        if df is None:
            history = self.provider.get_history(symbol, store_tf)
            if history is not None and len(history) > 0:
                self.store.load_history(symbol, history, store_tf)
                df = self.store.get_data(symbol, store_tf)

        if df is None:
            return None

        if timeframe == "D":
            return df

        # Resample logic using pandas
        df_to_resample = df.copy()

        # Convert index to datetime for resampling
        if not isinstance(df_to_resample.index, pd.DatetimeIndex):
            df_to_resample.index = pd.to_datetime(df_to_resample.index, unit="s")

        # Resample mapping
        tf_map = {"W": "W", "M": "ME", "Y": "YE"}
        pandas_tf = tf_map.get(timeframe, "D")

        resampled = (
            df_to_resample.resample(pandas_tf)
            .agg(
                {
                    "open": "first",
                    "high": "max",
                    "low": "min",
                    "close": "last",
                    "volume": "sum",
                }
            )
            .dropna()
        )

        return resampled

    def get_ohlcv_series(
        self, symbol: str, limit: int | None = None
    ) -> list[list] | None:
        """Returns OHLCV data as a list of [t, o, h, l, c, v] rows.

        Ordered chronologically by timestamp (latest first).
        """
        df = self.store.get_data(symbol)
        if df is None:
            return None

        # Prepare for series output: [timestamp, open, high, low, close, volume]
        export_df = df.reset_index()[
            ["timestamp", "open", "high", "low", "close", "volume"]
        ]

        # Latest first
        export_df = export_df.iloc[::-1]

        if limit is not None and limit > 0:
            export_df = export_df.iloc[:limit]

        return export_df.values.tolist()
