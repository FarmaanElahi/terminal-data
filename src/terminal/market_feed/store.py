"""Efficient OHLC store using pre-allocated numpy ring buffers.

Supports multiple timeframes per symbol via (symbol, timeframe) composite keys.

Storage layout per (symbol, timeframe):
  - timestamps: int64 array   (Unix seconds)
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

# Maps both short formula names (C, H, …) and long names (close, high, …)
# to their index in the ohlcv array.  Used by get_last_field() fast path.
_FIELD_NAME_TO_IDX: dict[str, int] = {
    # Short names — as emitted by the formula FieldRef node
    "O": 0, "H": 1, "L": 2, "C": 3, "V": 4,
    # Long names — in case a formula uses full column names
    "OPEN": 0, "HIGH": 1, "LOW": 2, "CLOSE": 3, "VOLUME": 4,
}

# Type alias for the composite key
type StoreKey = tuple[str, str]  # (symbol, timeframe)

_DEFAULT_TF = "1D"


class OHLCStore:
    """Ring-buffer OHLC store with O(1) realtime updates.

    All data is keyed by ``(symbol, timeframe)`` to support multiple
    resolutions for the same instrument simultaneously.
    """

    def __init__(self, capacity_per_symbol: int = 10000):
        self.capacity = capacity_per_symbol
        # Per-(symbol, timeframe) storage
        self._timestamps: dict[StoreKey, np.ndarray] = {}  # int64
        self._ohlcv: dict[StoreKey, np.ndarray] = {}  # float32, shape (cap, 5)
        self._sizes: dict[StoreKey, int] = {}
        self._locks: dict[StoreKey, asyncio.Lock] = {}

    @staticmethod
    def _key(symbol: str, timeframe: str = _DEFAULT_TF) -> StoreKey:
        return (symbol, timeframe)

    def _ensure_key(self, key: StoreKey) -> None:
        """Allocate storage for a (symbol, timeframe) if not already present."""
        if key not in self._ohlcv:
            self._timestamps[key] = np.zeros(self.capacity, dtype=np.int64)
            self._ohlcv[key] = np.zeros((self.capacity, _NUM_COLS), dtype=np.float32)
            self._sizes[key] = 0
            self._locks[key] = asyncio.Lock()

    def load_history(
        self, symbol: str, history: pd.DataFrame, timeframe: str = _DEFAULT_TF
    ) -> None:
        """Load historical data for a symbol at a given timeframe from a DataFrame.

        Expects columns: open, high, low, close, volume.
        Index should be named 'timestamp' (int seconds).
        """
        key = self._key(symbol, timeframe)
        self._ensure_key(key)

        if history is None or len(history) == 0:
            return

        # Defensive: ensure chronological order and deduplicate timestamps
        if not history.index.is_monotonic_increasing:
            history = history.sort_index()
        # Drop duplicate timestamps, keeping the last (most recent) value
        history = history[~history.index.duplicated(keep="last")]

        n = min(len(history), self.capacity)
        if n == 0:
            return

        # Take the last `n` rows if history exceeds capacity
        if len(history) > self.capacity:
            history = history.iloc[-self.capacity:]

        # Extract timestamps from index
        ts = history.index.values
        if hasattr(ts, "astype"):
            self._timestamps[key][:n] = ts[-n:].astype(np.int64)
        else:
            self._timestamps[key][:n] = np.array(ts[-n:], dtype=np.int64)

        # Extract OHLCV values
        for i, col in enumerate(_OHLCV_COLS):
            self._ohlcv[key][:n, i] = history[col].values[-n:].astype(np.float32)

        self._sizes[key] = n

    def add_realtime(
        self, symbol: str, candle: tuple, timeframe: str = _DEFAULT_TF
    ) -> None:
        """Update the store with a realtime candle.

        candle: (timestamp, open, high, low, close, volume)
        If the timestamp matches the last entry, update in-place.
        Otherwise append a new row.
        """
        key = self._key(symbol, timeframe)
        self._ensure_key(key)

        ts = int(candle[0])
        size = self._sizes[key]
        values = np.array(
            [candle[1], candle[2], candle[3], candle[4], candle[5]],
            dtype=np.float32,
        )

        if size > 0 and self._timestamps[key][size - 1] == ts:
            # Update existing row in-place
            self._ohlcv[key][size - 1] = values
        else:
            # Append new row
            if size >= self.capacity:
                # Ring buffer: shift left by one
                self._timestamps[key][:-1] = self._timestamps[key][1:]
                self._ohlcv[key][:-1] = self._ohlcv[key][1:]
                idx = self.capacity - 1
            else:
                idx = size
                self._sizes[key] = size + 1

            self._timestamps[key][idx] = np.int64(ts)
            self._ohlcv[key][idx] = values

    def get_data(
        self, symbol: str, timeframe: str = _DEFAULT_TF
    ) -> pd.DataFrame | None:
        """Return a DataFrame view for a symbol at a timeframe, or None if not loaded."""
        key = self._key(symbol, timeframe)
        if key not in self._ohlcv:
            return None

        size = self._sizes.get(key, 0)
        if size == 0:
            return None

        ts = self._timestamps[key][:size]
        data = self._ohlcv[key][:size]

        df = pd.DataFrame(
            data,
            columns=list(_OHLCV_COLS),
            index=pd.Index(ts, name="timestamp"),
        )
        # Expose timestamp as a regular column too, so formula fields
        # like T / TIMESTAMP can reference it with full capabilities
        # (shifting, comparisons, arithmetic).
        df["timestamp"] = ts.astype(np.float64)
        return df

    def get_all_data(
        self, timeframe: str = _DEFAULT_TF
    ) -> dict[str, pd.DataFrame]:
        """Return DataFrames for all symbols at a given timeframe."""
        result = {}
        for key in self._ohlcv:
            sym, tf = key
            if tf != timeframe:
                continue
            df = self.get_data(sym, tf)
            if df is not None:
                result[sym] = df
        return result

    def has_symbol(self, symbol: str, timeframe: str = _DEFAULT_TF) -> bool:
        """Check whether a symbol is loaded at a given timeframe."""
        key = self._key(symbol, timeframe)
        return key in self._ohlcv and self._sizes.get(key, 0) > 0

    def get_last_n_data(
        self, symbol: str, n: int, timeframe: str = _DEFAULT_TF
    ) -> pd.DataFrame | None:
        """Return the last *n* rows as a DataFrame without allocating the full history.

        Building a 50-row DataFrame for ``SMA(C, 50)`` is ~36× cheaper than
        building the full 1825-row one and then slicing it away.  The caller
        already knows the minimum rows it needs via the static lookback analysis,
        so this is always safe.

        Returns ``None`` if the symbol is not loaded.
        """
        key = self._key(symbol, timeframe)
        if key not in self._ohlcv:
            return None

        size = self._sizes.get(key, 0)
        if size == 0:
            return None

        actual_n = min(n, size)
        start = size - actual_n

        ts = self._timestamps[key][start:size]
        data = self._ohlcv[key][start:size]

        df = pd.DataFrame(
            data,
            columns=list(_OHLCV_COLS),
            index=pd.Index(ts.copy(), name="timestamp"),
        )
        df["timestamp"] = ts.astype(np.float64)
        return df

    def get_last_field(
        self, symbol: str, field_name: str, timeframe: str = _DEFAULT_TF
    ) -> float | None:
        """Return the last value of a single OHLCV field without allocating a DataFrame.

        ``field_name`` accepts both the short formula form (``C``, ``H``, ``L``,
        ``O``, ``V``) and the long column name (``close``, ``high``, etc.).

        Returns ``None`` if the symbol is not yet loaded or the field is unknown.
        This is an O(1) operation — a single array element read with no copies.
        """
        key = self._key(symbol, timeframe)
        size = self._sizes.get(key, 0)
        if size == 0:
            return None
        idx = _FIELD_NAME_TO_IDX.get(field_name.upper())
        if idx is None:
            return None
        return float(self._ohlcv[key][size - 1, idx])

    def get_lock(self, symbol: str, timeframe: str = _DEFAULT_TF) -> asyncio.Lock:
        """Return the asyncio.Lock for a given (symbol, timeframe) pair."""
        key = self._key(symbol, timeframe)
        if key not in self._locks:
            self._locks[key] = asyncio.Lock()
        return self._locks[key]
