"""Efficient OHLC store using pre-allocated numpy ring buffers.

Storage layout per symbol:
  - timestamps: int32 array   (Unix seconds, ~68 year range)
  - ohlcv:      float32 array  (capacity × 5)
  - size:       int            (current row count)

DataFrames are constructed lazily on demand via ``get_data()``.
"""

import asyncio
import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Column order in the ohlcv array
_OHLCV_COLS = ("open", "high", "low", "close", "volume")
_NUM_COLS = len(_OHLCV_COLS)


class OHLCStore:
    """Ring-buffer OHLC store with O(1) realtime updates."""

    def __init__(self, capacity_per_symbol: int = 10000):
        self.capacity = capacity_per_symbol
        # Per-symbol storage
        self._timestamps: dict[str, np.ndarray] = {}  # int32
        self._ohlcv: dict[str, np.ndarray] = {}  # float32, shape (cap, 5)
        self._sizes: dict[str, int] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self.is_dirty = False

    def _ensure_symbol(self, symbol: str) -> None:
        """Allocate storage for a symbol if not already present."""
        if symbol not in self._ohlcv:
            self._timestamps[symbol] = np.zeros(self.capacity, dtype=np.int32)
            self._ohlcv[symbol] = np.zeros((self.capacity, _NUM_COLS), dtype=np.float32)
            self._sizes[symbol] = 0
            self._locks[symbol] = asyncio.Lock()

    def load_history(self, symbol: str, history: pd.DataFrame) -> None:
        """Load historical data for a symbol from a DataFrame.

        Expects columns: open, high, low, close, volume.
        Index should be named 'timestamp' (int seconds).
        """
        self._ensure_symbol(symbol)

        n = min(len(history), self.capacity)
        if n == 0:
            return

        # Take the last `n` rows if history exceeds capacity
        if len(history) > self.capacity:
            history = history.iloc[-self.capacity :]

        # Extract timestamps from index
        ts = history.index.values
        if hasattr(ts, "astype"):
            self._timestamps[symbol][:n] = ts[-n:].astype(np.int32)
        else:
            self._timestamps[symbol][:n] = np.array(ts[-n:], dtype=np.int32)

        # Extract OHLCV values
        for i, col in enumerate(_OHLCV_COLS):
            self._ohlcv[symbol][:n, i] = history[col].values[-n:].astype(np.float32)

        self._sizes[symbol] = n
        self.is_dirty = True

    def add_realtime(self, symbol: str, candle: tuple) -> None:
        """Update the store with a realtime candle.

        candle: (timestamp, open, high, low, close, volume)
        If the timestamp matches the last entry, update in-place.
        Otherwise append a new row.
        """
        self._ensure_symbol(symbol)

        ts = int(candle[0])
        size = self._sizes[symbol]
        values = np.array(
            [candle[1], candle[2], candle[3], candle[4], candle[5]],
            dtype=np.float32,
        )

        if size > 0 and self._timestamps[symbol][size - 1] == ts:
            # Update existing row in-place
            self._ohlcv[symbol][size - 1] = values
        else:
            # Append new row
            if size >= self.capacity:
                # Ring buffer: shift left by one
                self._timestamps[symbol][:-1] = self._timestamps[symbol][1:]
                self._ohlcv[symbol][:-1] = self._ohlcv[symbol][1:]
                idx = self.capacity - 1
            else:
                idx = size
                self._sizes[symbol] = size + 1

            self._timestamps[symbol][idx] = np.int32(ts)
            self._ohlcv[symbol][idx] = values

        self.is_dirty = True

    def get_data(self, symbol: str) -> pd.DataFrame | None:
        """Return a DataFrame view for a symbol, or None if not loaded."""
        if symbol not in self._ohlcv:
            return None

        size = self._sizes.get(symbol, 0)
        if size == 0:
            return None

        ts = self._timestamps[symbol][:size]
        data = self._ohlcv[symbol][:size]

        df = pd.DataFrame(
            data,
            columns=list(_OHLCV_COLS),
            index=pd.Index(ts, name="timestamp"),
        )
        return df

    def get_all_data(self) -> dict[str, pd.DataFrame]:
        """Return DataFrames for all symbols."""
        result = {}
        for symbol in self._ohlcv:
            df = self.get_data(symbol)
            if df is not None:
                result[symbol] = df
        return result

    def has_symbol(self, symbol: str) -> bool:
        """Check whether a symbol is loaded in the store."""
        return symbol in self._ohlcv and self._sizes.get(symbol, 0) > 0

    def get_lock(self, symbol: str) -> asyncio.Lock:
        """Return the asyncio.Lock for a given symbol (for lazy loading)."""
        if symbol not in self._locks:
            self._locks[symbol] = asyncio.Lock()
        return self._locks[symbol]
