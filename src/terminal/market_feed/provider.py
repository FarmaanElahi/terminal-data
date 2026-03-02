from abc import ABC
from fsspec import AbstractFileSystem

from pathlib import Path
import pandas as pd
import logging
from typing import Dict

logger = logging.getLogger(__name__)


class DataProvider(ABC):
    """
    Abstract base class for providing OHLC data.
    Stores history as Dict[str, pd.DataFrame] — no numpy intermediate.
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
        self._history_dict: Dict[str, pd.DataFrame] = {}
        self._cache_loaded = False

    def load_cache(self):
        """Loads the entire Parquet cache into memory as DataFrames."""
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
                hist = group[
                    ["timestamp", "open", "high", "low", "close", "volume"]
                ].copy()

                # Convert timestamp to int32 seconds
                if pd.api.types.is_datetime64_any_dtype(hist["timestamp"]):
                    hist["timestamp"] = (
                        hist["timestamp"]
                        .values.astype("datetime64[s]")
                        .astype("int64")
                        .astype("int32")
                    )
                else:
                    hist["timestamp"] = hist["timestamp"].astype("int32")

                # Downcast OHLCV to float32
                for col in ("open", "high", "low", "close", "volume"):
                    hist[col] = hist[col].astype("float32")

                hist = hist.sort_values("timestamp")
                hist = hist.set_index("timestamp")
                self._history_dict[str(symbol)] = hist

            logger.info(f"Loaded {len(self._history_dict)} symbols from cache.")
        except Exception as e:
            logger.error(f"Error reading local cache: {e}")
        finally:
            self._cache_loaded = True

    def _sync_from_oci(self):
        max_retries = 3
        for attempt in range(max_retries):
            try:
                if self.fs.exists(self.cache_file_oci):
                    self.fs.get(self.cache_file_oci, str(self.cache_file_local))
                    logger.info(f"Synced cache from OCI: {self.cache_file_oci}")
                    return
                else:
                    logger.info("OCI cache file does not exist: %s", self.cache_file_oci)
                    return
            except Exception as e:
                logger.warning(
                    "OCI sync attempt %d/%d failed: %s",
                    attempt + 1,
                    max_retries,
                    e,
                )
                if attempt == max_retries - 1:
                    if self.cache_file_local.exists():
                        logger.warning(
                            "OCI unreachable after %d retries — using local cache",
                            max_retries,
                        )
                    else:
                        logger.error(
                            "OCI unreachable and no local cache available"
                        )

    def get_history(self, symbol: str) -> pd.DataFrame | None:
        """
        Retrieves historical data for a symbol as a DataFrame.
        Returns None if no data available.
        """
        if not self._cache_loaded:
            self.load_cache()
        return self._history_dict.get(symbol)

    def get_all_tickers(self) -> list[str]:
        """
        Returns all tickers loaded in the cache.
        """
        if not self._cache_loaded:
            self.load_cache()
        return list(self._history_dict.keys())

    def update_cache(self, df: pd.DataFrame):
        """
        Persists data to local Parquet + OCI (seeding only).
        In-memory cache is populated once via load_cache() at startup.
        Uses ZSTD compression for smaller Parquet files.
        """
        try:
            df.to_parquet(self.cache_file_local, index=False, compression="zstd")
            self.fs.put(str(self.cache_file_local), self.cache_file_oci)
            logger.info(f"Saved cache to OCI: {self.cache_file_oci}")
        except Exception as e:
            logger.error(f"Failed to save cache: {e}")
