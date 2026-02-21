import asyncio
import logging
import weakref
from typing import List, Optional, AsyncGenerator

import pandas as pd
from fsspec import AbstractFileSystem

from .store import OHLCStore
from .provider import DataProvider
from .tradingview import TradingViewDataProvider
from terminal.config import Settings
from terminal.symbols import service as symbol_service

logger = logging.getLogger(__name__)


class MarketDataManager:
    """
    Coordinates data loading and realtime updates between OHLCStore and DataProvider.
    """

    def __init__(self, store: OHLCStore, provider: DataProvider):
        self.store = store
        self.provider = provider
        self._streaming_task: Optional[asyncio.Task] = None
        self._cache_updater_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        self._subscribers: weakref.WeakSet[asyncio.Queue] = weakref.WeakSet()

    async def start(
        self,
        fs: AbstractFileSystem,
        settings: Settings,
        markets: Optional[List[str]] = None,
    ):
        """
        Proactively loads all symbols from the symbol service, loads their history from cache,
        fetches any missing history from the provider, and starts realtime streaming.
        """
        try:
            logger.info("Starting MarketDataManager...")
            # 1. Fetch all symbols
            tickers = await symbol_service.all_ticker(fs, settings)

            if not tickers:
                logger.warning("No symbols found from symbol service.")
                return

            logger.info(f"Loaded {len(tickers)} symbols from symbol service.")

            # 2. Load history (this uses cache or provider fallback)
            await self.load_history(tickers)

            # 3. Start realtime streaming and cache updater
            await self.start_realtime_streaming(tickers)
            self._start_periodic_cache_updater()
        except Exception as e:
            logger.error(f"Failed to start MarketDataManager: {e}", exc_info=True)

    async def load_history(self, symbols: List[str]):
        """
        Loads historical data for a list of symbols into the store.
        """
        logger.info(f"Loading history for {len(symbols)} symbols...")

        # Load batch history from cache (fast)
        for symbol in symbols:
            try:
                history = self.provider.get_history(symbol)
                if len(history) > 0:
                    self.store.load_history(symbol, history)
            except Exception as e:
                logger.error(f"Failed to load history for {symbol}: {e}")

    async def start_realtime_streaming(self, tickers: List[str]):
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

    async def _stream_loop(self, tickers: List[str]):
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
                    self._publish(ticker, candle)

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

                        # Copy to avoid modifying the original and add symbol column
                        df_copy = df.copy()
                        df_copy["symbol"] = ticker
                        # We need to reset the index to include timestamp in the cache
                        df_copy.reset_index(inplace=True)
                        # Remove aliases before caching if they are not needed in storage
                        # But for now, let's just keep whatever columns are there
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

    def _publish(self, symbol: str, candle: tuple):
        """
        Publishes a real-time candle update to all subscribers.
        """
        update = {"symbol": symbol, "candle": candle}
        for q in list(self._subscribers):
            try:
                q.put_nowait(update)
            except asyncio.QueueFull:
                pass

    async def subscribe(
        self, symbol: Optional[str] = None
    ) -> AsyncGenerator[dict, None]:
        """
        Allows modules to subscribe to real-time bar updates.
        If symbol is provided, yields updates only for that symbol.
        Otherwise, yields all updates.
        """
        q = asyncio.Queue(maxsize=1000)
        self._subscribers.add(q)

        try:
            while not self._stop_event.is_set():
                try:
                    update = await asyncio.wait_for(q.get(), timeout=1.0)
                    if symbol is None or update["symbol"] == symbol:
                        yield update
                except asyncio.TimeoutError:
                    continue
        except asyncio.CancelledError:
            pass
        finally:
            self._subscribers.discard(q)

    def get_data(self, symbol: str):
        """
        Convenience method to get data from the underlying store.
        """
        return self.store.get_data(symbol)

    def get_ohlcv(self, symbol: str, timeframe: str = "D") -> Optional[pd.DataFrame]:
        """
        Returns OHLCV data as a pandas DataFrame.
        Resamples the data if a higher timeframe (W, M, Y) is requested.
        """
        df = self.store.get_data(symbol)
        if df is None:
            return None

        if timeframe == "D":
            return df

        # Resample logic using pandas
        # Ensure we don't modify the original buffer
        df_to_resample = df.copy()

        # Convert index to datetime for resampling
        # If it's already datetime, no need to convert
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

        # Add aliases back to resampled data
        resampled["O"] = resampled["open"]
        resampled["H"] = resampled["high"]
        resampled["L"] = resampled["low"]
        resampled["C"] = resampled["close"]
        resampled["V"] = resampled["volume"]

        # Optionally convert back to numeric index if needed,
        # but scan engine should work fine with datetime index or we can convert it
        return resampled

    def get_ohlcv_series(
        self, symbol: str, limit: Optional[int] = None
    ) -> Optional[List[List]]:
        """
        Returns OHLCV data as a list of [t, o, h, l, c, v] rows.
        Ordered chronologically by timestamp (latest first).
        """
        df = self.store.get_data(symbol)
        if df is None:
            return None

        # Prepare for series output: [timestamp, open, high, low, close, volume]
        # Reset index to get timestamp column
        export_df = df.reset_index()[
            ["timestamp", "open", "high", "low", "close", "volume"]
        ]

        # Latest first
        export_df = export_df.iloc[::-1]

        if limit is not None and limit > 0:
            export_df = export_df.iloc[:limit]

        return export_df.values.tolist()
