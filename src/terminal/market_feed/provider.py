from abc import ABC
import numpy as np
from fsspec import AbstractFileSystem


from pathlib import Path
import pandas as pd
import logging
from typing import Dict
from terminal.market_feed.models import CANDLE_DTYPE

logger = logging.getLogger(__name__)


class DataProvider(ABC):
    """
    Abstract base class for providing OHLC data.
    """

    def __init__(
        self,
        fs: AbstractFileSystem,
        bucket: str,
        cache_dir: str = "data",
        provider_name: str = "tv",
    ):
        self.fs = fs
        self.bucket = bucket
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file_local = self.cache_dir / f"{provider_name}_candles.parquet"
        self.cache_file_oci = f"{bucket}/market_feed/candles_{provider_name}.parquet"
        self._history_dict: Dict[str, np.ndarray] = {}
        self._cache_loaded = False

    def load_cache(self):
        """Loads the entire Parquet cache into memory once."""
        if self._cache_loaded:
            return

        if not self.cache_file_local.exists():
            self._sync_from_oci()

        if not self.cache_file_local.exists():
            self._cache_loaded = True
            return

        try:
            df = pd.read_parquet(self.cache_file_local)
            if df.empty:
                self._cache_loaded = True
                return

            for symbol, group in df.groupby("symbol"):
                history = np.zeros(len(group), dtype=CANDLE_DTYPE)
                history["timestamp"] = (
                    group["timestamp"].values.astype("datetime64[s]").astype("int64")
                )
                history["open"] = group["open"].values
                history["high"] = group["high"].values
                history["low"] = group["low"].values
                history["close"] = group["close"].values
                history["volume"] = group["volume"].values
                history = np.sort(history, order="timestamp")
                self._history_dict[symbol] = history

            logger.info(f"Loaded {len(self._history_dict)} symbols from cache.")
        except Exception as e:
            logger.error(f"Error reading local cache: {e}")
        finally:
            self._cache_loaded = True

    def _sync_from_oci(self):
        try:
            if self.fs.exists(self.cache_file_oci):
                self.fs.get(self.cache_file_oci, str(self.cache_file_local))
                logger.info(f"Synced cache from OCI: {self.cache_file_oci}")
        except Exception as e:
            logger.error(f"Failed to sync from OCI: {e}")

    def get_history(self, symbol: str) -> np.ndarray:
        """
        Retrieves historical data for a symbol from in-memory cache.
        """
        if not self._cache_loaded:
            self.load_cache()
        return self._history_dict.get(symbol, np.empty(0, dtype=CANDLE_DTYPE))

    def get_all_tickers(self) -> list[str]:
        """
        Returns all tickers loaded in the cache.
        """
        if not self._cache_loaded:
            self.load_cache()
        return list(self._history_dict.keys())

    def update_cache(self, df: pd.DataFrame):
        """
        Updates the internal cache backend with new historical data.
        """
        try:
            df.to_parquet(self.cache_file_local, index=False)
            self.fs.put(str(self.cache_file_local), self.cache_file_oci)
            logger.info(f"Saved cache to OCI: {self.cache_file_oci}")

            for symbol, group in df.groupby("symbol"):
                history = np.zeros(len(group), dtype=CANDLE_DTYPE)
                history["timestamp"] = (
                    group["timestamp"].values.astype("datetime64[s]").astype("int64")
                )
                history["open"] = group["open"].values
                history["high"] = group["high"].values
                history["low"] = group["low"].values
                history["close"] = group["close"].values
                history["volume"] = group["volume"].values
                history = np.sort(history, order="timestamp")
                self._history_dict[symbol] = history

        except Exception as e:
            logger.error(f"Failed to save cache: {e}")
