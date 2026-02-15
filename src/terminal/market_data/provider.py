from abc import ABC, abstractmethod
from typing import List, Dict, Optional
import numpy as np
import random
import time
from .types import CANDLE_DTYPE


class DataProvider(ABC):
    """
    Abstract base class for providing OHLC data.
    """

    @abstractmethod
    def get_history(self, symbol: str) -> np.ndarray:
        """
        Retrieves historical data for a symbol.
        """
        pass

    @abstractmethod
    def subscribe(self, symbols: List[str]):
        """
        Subscribes to realtime updates for a list of symbols.
        """
        pass

    @abstractmethod
    def unsubscribe(self, symbols: List[str]):
        """
        Unsubscribes from realtime updates for a list of symbols.
        """
        pass


class MockDataProvider(DataProvider):
    """
    Mock implementation of DataProvider for testing.
    Generates synthetic random walk data for historical and realtime simulation.
    """

    def __init__(self):
        self._subscribed_symbols: List[str] = []

    def get_history(self, symbol: str, periods: int = 100) -> np.ndarray:
        """
        Generates synthetic historical data (random walk).
        """
        if periods <= 0:
            return np.empty(0, dtype=CANDLE_DTYPE)

        history = np.zeros(periods, dtype=CANDLE_DTYPE)

        # Start with a base price
        base_price = 100.0
        start_timestamp = int(time.time()) - (periods * 86400)  # Daily candles

        prices = [base_price]
        for i in range(1, periods):
            change = random.uniform(-2.0, 2.0)
            prices.append(prices[-1] + change)

        for i in range(periods):
            close_price = prices[i]
            open_price = close_price + random.uniform(-1.0, 1.0)
            high_price = max(open_price, close_price) + random.uniform(0.0, 1.0)
            low_price = min(open_price, close_price) - random.uniform(0.0, 1.0)
            volume = random.randint(1000, 10000)
            timestamp = start_timestamp + (i * 86400)

            history[i] = (
                timestamp,
                open_price,
                high_price,
                low_price,
                close_price,
                volume,
            )

        return history

    def subscribe(self, symbols: List[str]):
        """
        Just tracks subscribed symbols for mock purposes.
        """
        for s in symbols:
            if s not in self._subscribed_symbols:
                self._subscribed_symbols.append(s)

    def unsubscribe(self, symbols: List[str]):
        """
        Removes symbols from subscription list.
        """
        for s in symbols:
            if s in self._subscribed_symbols:
                self._subscribed_symbols.remove(s)

    def generate_realtime_candle(
        self, symbol: str, timestamp: Optional[int] = None
    ) -> tuple:
        """
        Generates a single realtime candle update.
        """
        base_price = 100.0  # Just a placeholder base

        # In a real mock, we might want to carry over the last price from history
        # For simplicity, generating independent random candle

        close_price = base_price + random.uniform(-5.0, 5.0)
        open_price = close_price + random.uniform(-1.0, 1.0)
        high_price = max(open_price, close_price) + random.uniform(0.0, 1.0)
        low_price = min(open_price, close_price) - random.uniform(0.0, 1.0)
        volume = random.randint(100, 500)

        if timestamp is None:
            timestamp = int(time.time())

        return (timestamp, open_price, high_price, low_price, close_price, volume)
