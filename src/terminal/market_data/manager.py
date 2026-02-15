import asyncio
import logging
from typing import List, Optional
import numpy as np
from .store import OHLCStore
from .provider import DataProvider
from .tradingview import TradingViewDataProvider

logger = logging.getLogger(__name__)


class MarketDataManager:
    """
    Coordinates data loading and realtime updates between OHLCStore and DataProvider.
    """

    def __init__(self, store: OHLCStore, provider: DataProvider):
        self.store = store
        self.provider = provider
        self._polling_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()

    async def load_history(self, symbols: List[str]):
        """
        Loads historical data for a list of symbols into the store.
        """
        logger.info(f"Loading history for {len(symbols)} symbols...")
        for symbol in symbols:
            try:
                history = self.provider.get_history(symbol)
                if len(history) > 0:
                    self.store.load_history(symbol, history)
                    logger.debug(f"Loaded history for {symbol}")
            except Exception as e:
                logger.error(f"Failed to load history for {symbol}: {e}")

    async def start_realtime_polling(
        self, markets: List[str] = ["india"], interval: int = 60
    ):
        """
        Starts the background polling task for realtime updates.
        """
        if self._polling_task and not self._polling_task.done():
            logger.warning("Realtime polling is already running.")
            return

        if not isinstance(self.provider, TradingViewDataProvider):
            raise TypeError("Realtime polling requires a TradingViewDataProvider.")

        self._stop_event.clear()
        self._polling_task = asyncio.create_task(self._poll_loop(markets, interval))
        logger.info(f"Started realtime polling for {markets}")

    async def stop_realtime_polling(self):
        """
        Stops the background polling task.
        """
        if self._polling_task:
            self._stop_event.set()
            await self._polling_task
            self._polling_task = None
            logger.info("Stopped realtime polling.")

    async def _poll_loop(self, markets: List[str], interval: int):
        """
        Internal loop for polling realtime data.
        """
        while not self._stop_event.is_set():
            try:
                # Type hint for provider since we checked it in start_realtime_polling
                provider: TradingViewDataProvider = self.provider
                updates = await provider.fetch_realtime(markets=markets)
                logger.debug(f"Fetched {len(updates)} realtime updates")

                for update in updates:
                    candle = (
                        update["timestamp"],
                        update["open"],
                        update["high"],
                        update["low"],
                        update["close"],
                        update["volume"],
                    )
                    self.store.add_realtime(update["ticker"], candle)

            except Exception as e:
                logger.error(f"Error in realtime polling loop: {e}")

            try:
                # Wait for interval or until stopped
                await asyncio.wait_for(self._stop_event.wait(), timeout=interval)
            except asyncio.TimeoutError:
                # Normal timeout, continue loop
                pass

    def get_data(self, symbol: str):
        """
        Convenience method to get data from the underlying store.
        """
        return self.store.get_data(symbol)

    def get_ohlcv(self, symbol: str) -> Optional[dict[str, np.ndarray]]:
        """
        Returns OHLCV data as a dictionary of separate numpy columns.
        Each column is a 1D numpy array ordered by timestamp.
        """
        data = self.store.get_data(symbol)
        if data is None:
            return None

        return {
            "timestamp": data["timestamp"],
            "open": data["open"],
            "high": data["high"],
            "low": data["low"],
            "close": data["close"],
            "volume": data["volume"],
        }

    def get_ohlcv_series(self, symbol: str) -> Optional[List[List]]:
        """
        Returns OHLCV data as a list of [t, o, h, l, c, v] rows.
        Ordered chronologically by timestamp.
        """
        data = self.store.get_data(symbol)
        if data is None:
            return None

        # Convert structured numpy array to list of tuples (JSON serializes tuples as lists)
        # We use [::-1] to reverse the order so the latest candle is first
        return data[::-1].tolist()
