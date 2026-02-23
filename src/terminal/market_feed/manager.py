import asyncio
import logging
from typing import AsyncGenerator

import pandas as pd

from .store import OHLCStore
from .provider import DataProvider
from .tradingview import TradingViewDataProvider

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

    async def subscribe(self, symbol: str | None = None) -> AsyncGenerator[dict, None]:
        """Yield ``{"symbol": ..., "candle": ...}`` dicts on each update.

        If *symbol* is given, only yields updates for that symbol.
        """
        last_version = self._version
        while True:
            async with self._condition:
                await self._condition.wait_for(lambda: self._version > last_version)
                current_version = self._version
            # Yield updates since last wakeup
            for sym, candle in list(self._latest.items()):
                if symbol is not None and sym != symbol:
                    continue
                yield {"symbol": sym, "candle": candle}
            last_version = current_version


class MarketDataManager:
    """
    Coordinates data loading and realtime updates between OHLCStore and DataProvider.
    """

    def __init__(self, store: OHLCStore, provider: DataProvider):
        self.store = store
        self.provider = provider
        self._streaming_task: asyncio.Task | None = None
        self._cache_updater_task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()
        self._broadcast = BroadcastChannel()

    async def start(self):
        """
        Loads all symbols from the provider cache, loads their history from cache,
        and starts realtime streaming.
        """
        try:
            logger.info("Starting MarketDataManager...")
            # 1. Fetch all symbols from provider cache
            tickers = self.provider.get_all_tickers()

            if not tickers:
                logger.warning("No symbols found from provider cache.")
                return

            logger.info(f"Loaded {len(tickers)} symbols from provider cache.")

            # 2. Load history (batch — DataFrames direct from provider)
            await self.load_history(tickers)

            # 3. Start realtime streaming and cache updater
            await self.start_realtime_streaming(tickers)
            self._start_periodic_cache_updater()
        except Exception as e:
            logger.error(f"Failed to start MarketDataManager: {e}", exc_info=True)

    async def load_history(self, symbols: list[str]):
        """
        Loads historical data for a list of symbols into the store.
        Provider returns DataFrames directly — no numpy intermediate.
        """
        logger.info(f"Loading history for {len(symbols)} symbols...")

        for symbol in symbols:
            try:
                history = self.provider.get_history(symbol)
                if history is not None and len(history) > 0:
                    self.store.load_history(symbol, history)
            except Exception as e:
                logger.error(f"Failed to load history for {symbol}: {e}")

    async def start_realtime_streaming(self, tickers: list[str]):
        """
        Starts the background streaming task for realtime updates using websocket quotes.
        """
        if self._streaming_task and not self._streaming_task.done():
            logger.warning("Realtime streaming is already running.")
            return

        if not isinstance(self.provider, TradingViewDataProvider):
            raise TypeError("Realtime streaming requires a TradingViewDataProvider.")

        self._stop_event.clear()
        self._streaming_task = asyncio.create_task(self._stream_loop(tickers))
        logger.info(f"Started realtime streaming for {len(tickers)} tickers")

    async def stop_realtime_streaming(self):
        """
        Stops the background tasks.
        """
        self._stop_event.set()
        if self._streaming_task:
            self._streaming_task.cancel()
            self._streaming_task = None
        if self._cache_updater_task:
            self._cache_updater_task.cancel()
            self._cache_updater_task = None
        logger.info("Stopped realtime streaming and cache updater.")

    async def _stream_loop(self, tickers: list[str]):
        """
        Internal loop for streaming realtime data from streamer2 quote stream.
        """
        try:
            # Type hint for provider
            provider: TradingViewDataProvider = self.provider

            # Fields we need from streamer2 for our ohlcv
            fields = [
                "open_price",
                "high_price",
                "low_price",
                "lp",
                "volume",
                "open_time",
            ]

            async for quote_dict in provider._tv.streamer.stream_quotes(
                tickers, fields=fields
            ):
                if self._stop_event.is_set():
                    break

                for ticker, quote in quote_dict.items():
                    # Translate streamer2 fields to OHLCV format
                    timestamp = quote.get("open_time")
                    if not timestamp:
                        continue

                    # Determine current values, fallback to previous if missing in the tick
                    open_p = quote.get("open_price") or quote.get("lp")
                    high_p = quote.get("high_price") or quote.get("lp")
                    low_p = quote.get("low_price") or quote.get("lp")
                    close_p = quote.get("lp")
                    volume_p = quote.get("volume", 0)

                    if None in (open_p, high_p, low_p, close_p):
                        continue

                    candle = (
                        timestamp,
                        float(open_p),
                        float(high_p),
                        float(low_p),
                        float(close_p),
                        float(volume_p),
                    )

                    self.store.add_realtime(ticker, candle)
                    await self._broadcast.publish(ticker, candle)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error in realtime stream loop: {e}", exc_info=True)

    def _start_periodic_cache_updater(self):
        """
        Starts the background task to periodically write the cache.
        """
        if self._cache_updater_task and not self._cache_updater_task.done():
            return

        self._cache_updater_task = asyncio.create_task(self._periodic_cache_update())

    async def _periodic_cache_update(self, interval: int = 900):
        """
        Periodically checks the dirty flag and updates cache if needed.
        """
        while not self._stop_event.is_set():
            try:
                await asyncio.sleep(interval)

                if self.store.is_dirty:
                    logger.info("Store is dirty. Updating cache...")
                    all_data = self.store.get_all_data()

                    # Convert store to DataFrame
                    dfs = []
                    for ticker, df in all_data.items():
                        if df is None or len(df) == 0:
                            continue

                        df_copy = df.copy()
                        df_copy["symbol"] = ticker
                        df_copy.reset_index(inplace=True)
                        dfs.append(df_copy)

                    if dfs:
                        full_df = pd.concat(dfs, ignore_index=True)
                        self.provider.update_cache(full_df)
                        self.store.is_dirty = False
                        logger.info("Cache update complete and dirty flag reset.")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in periodic cache update: {e}", exc_info=True)

    async def subscribe(self, symbol: str | None = None) -> AsyncGenerator[dict, None]:
        """
        Allows modules to subscribe to real-time bar updates via broadcast channel.
        If symbol is provided, yields updates only for that symbol.
        Otherwise, yields all updates.
        """
        async for update in self._broadcast.subscribe(symbol):
            if self._stop_event.is_set():
                break
            yield update

    def get_data(self, symbol: str):
        """
        Convenience method to get data from the underlying store.
        """
        return self.store.get_data(symbol)

    def get_ohlcv(self, symbol: str, timeframe: str = "D") -> pd.DataFrame | None:
        """
        Returns OHLCV data as a pandas DataFrame.
        Resamples the data if a higher timeframe (W, M, Y) is requested.
        Lazy-loads from provider if symbol is not yet in the store.
        """
        df = self.store.get_data(symbol)

        # Lazy loading: if not in store, try loading from provider
        if df is None:
            history = self.provider.get_history(symbol)
            if history is not None and len(history) > 0:
                self.store.load_history(symbol, history)
                df = self.store.get_data(symbol)

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
        """
        Returns OHLCV data as a list of [t, o, h, l, c, v] rows.
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
