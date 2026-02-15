from abc import ABC, abstractmethod
import numpy as np


from pathlib import Path


class DataProvider(ABC):
    """
    Abstract base class for providing OHLC data.
    """

    def __init__(
        self, fs: any, bucket: str, cache_dir: str = "data", provider_name: str = "tv"
    ):
        self.fs = fs
        self.bucket = bucket
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file_local = self.cache_dir / f"{provider_name}_candles.parquet"
        self.cache_file_oci = f"{bucket}/market_feed/candles_1d.parquet"

    @abstractmethod
    def get_history(self, symbol: str) -> np.ndarray:
        """
        Retrieves historical data for a symbol.
        """
        pass
