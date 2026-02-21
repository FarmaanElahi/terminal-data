import pandas as pd
from typing import Dict, Optional
import numpy as np


class OHLCStore:
    """
    Efficient store for OHLC data using pandas DataFrames.
    Supports historical data loading and realtime updates for multiple symbols.
    Update happens by timestamp index.
    """

    def __init__(self, capacity_per_symbol: int = 10000):
        self.capacity = capacity_per_symbol
        self._buffers: Dict[str, pd.DataFrame] = {}
        self.is_dirty = False

    def _initialize_symbol(self, symbol: str):
        """Allocates an empty DataFrame for a symbol if it doesn't exist."""
        if symbol not in self._buffers:
            # Create an empty DataFrame with expected columns
            # Using timestamp as index for fast updates
            cols = ["open", "high", "low", "close", "volume"]
            df = pd.DataFrame(columns=cols)
            df.index.name = "timestamp"

            # Pre-add aliases for scan engine
            df["O"] = df["open"]
            df["H"] = df["high"]
            df["L"] = df["low"]
            df["C"] = df["close"]
            df["V"] = df["volume"]

            self._buffers[symbol] = df

    def load_history(self, symbol: str, history_data: np.ndarray):
        """
        Loads historical data for a symbol.
        Overwrites existing data.
        """
        self._initialize_symbol(symbol)

        # Convert structured numpy array to DataFrame
        df = pd.DataFrame(history_data)
        if "timestamp" in df.columns:
            df.set_index("timestamp", inplace=True)

        # Ensure aliases are present
        df["O"] = df["open"]
        df["H"] = df["high"]
        df["L"] = df["low"]
        df["C"] = df["close"]
        df["V"] = df["volume"]

        if len(df) > self.capacity:
            df = df.iloc[-self.capacity :]

        self._buffers[symbol] = df
        self.is_dirty = True

    def add_realtime(self, symbol: str, candle: tuple):
        """
        Updates the store with a realtime candle.
        If the candle timestamp matches the last one, it updates the last entry.
        Otherwise, it appends a new entry.
        """
        self._initialize_symbol(symbol)
        df = self._buffers[symbol]

        timestamp = candle[0]
        # candle tuple: (timestamp, open, high, low, close, volume)
        data = {
            "open": float(candle[1]),
            "high": float(candle[2]),
            "low": float(candle[3]),
            "close": float(candle[4]),
            "volume": float(candle[5]),
            "O": float(candle[1]),
            "H": float(candle[2]),
            "L": float(candle[3]),
            "C": float(candle[4]),
            "V": float(candle[5]),
        }

        # Update or append
        # pandas .loc can do both: if index exists it updates, if not it appends
        # However, we want to maintain the capacity limit and ensure order

        if timestamp in df.index:
            # Check if values actually changed to set dirty flag
            # This is a bit expensive, maybe just set dirty = True
            df.loc[timestamp] = data
            self.is_dirty = True
        else:
            # Append new row
            new_row = pd.Series(data, name=timestamp)
            df = pd.concat([df, pd.DataFrame([new_row])])

            # Maintain capacity
            if len(df) > self.capacity:
                df = df.iloc[-self.capacity :]

            self._buffers[symbol] = df
            self.is_dirty = True

    def get_data(self, symbol: str) -> Optional[pd.DataFrame]:
        """
        Returns the DataFrame for a symbol.
        """
        return self._buffers.get(symbol)

    def get_all_data(self) -> Dict[str, pd.DataFrame]:
        """
        Returns data for all symbols.
        """
        return self._buffers


ohlc_store = OHLCStore()
