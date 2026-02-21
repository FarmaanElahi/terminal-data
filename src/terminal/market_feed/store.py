from typing import Dict, Optional
import numpy as np
from .models import CANDLE_DTYPE


class OHLCStore:
    """
    Efficient store for OHLC data using preallocated numpy arrays.
    Supports historical data loading and realtime updates for multiple symbols.
    """

    def __init__(self, capacity_per_symbol: int = 10000):
        self.capacity = capacity_per_symbol
        self._buffers: Dict[str, np.ndarray] = {}
        self._pointers: Dict[str, int] = {}
        self.is_dirty = False

    def _initialize_symbol(self, symbol: str):
        """Allocates buffer for a symbol if it doesn't exist."""
        if symbol not in self._buffers:
            self._buffers[symbol] = np.zeros(self.capacity, dtype=CANDLE_DTYPE)
            self._pointers[symbol] = 0

    def load_history(self, symbol: str, history_data: np.ndarray):
        """
        Loads historical data for a symbol.
        Overwrites existing data and resets the pointer.
        """
        self._initialize_symbol(symbol)

        count = len(history_data)
        if count > self.capacity:
            # If history is larger than capacity, take the latest 'capacity' elements
            history_data = history_data[-self.capacity :]
            count = self.capacity

        self._buffers[symbol][:count] = history_data
        self._pointers[symbol] = count
        self.is_dirty = True

    def add_realtime(self, symbol: str, candle: tuple):
        """
        Updates the store with a realtime candle.
        If the candle timestamp matches the last one, it updates the last entry.
        Otherwise, it appends a new entry.
        """
        self._initialize_symbol(symbol)

        ptr = self._pointers[symbol]
        buffer = self._buffers[symbol]

        # Check if we have any data
        if ptr > 0:
            last_idx = ptr - 1
            last_timestamp = buffer[last_idx]["timestamp"]
            new_timestamp = candle[0]  # Assuming timestamp is the first element

            if new_timestamp == last_timestamp:
                old_candle = tuple(buffer[last_idx])
                if old_candle != candle:
                    self.is_dirty = True
                    # Update existing candle
                    buffer[last_idx] = candle
                return

        # Append new candle
        self.is_dirty = True
        if ptr < self.capacity:
            buffer[ptr] = candle
            self._pointers[symbol] += 1
        else:
            # Buffer full, shift data (expensive, but hopefully rare with large capacity)
            # For now, shift left and append
            buffer[:-1] = buffer[1:]
            buffer[-1] = candle
            # Pointer stays at capacity

    def get_data(self, symbol: str) -> Optional[np.ndarray]:
        """
        Returns a view of the valid data for a symbol.
        """
        if symbol not in self._buffers:
            return None

        count = self._pointers[symbol]
        return self._buffers[symbol][:count]

    def get_all_data(self) -> Dict[str, np.ndarray]:
        """
        Returns data for all symbols.
        """
        result = {}
        for symbol in self._buffers:
            result[symbol] = self.get_data(symbol)
        return result
