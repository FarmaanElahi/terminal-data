import logging
import pandas as pd
import numpy as np
from typing import List

from .provider import DataProvider
from .models import CANDLE_DTYPE
from terminal.tradingview import TradingView

logger = logging.getLogger(__name__)


class TradingViewDataProvider(DataProvider):
    """
    DataProvider that fetches historical 1D candles from TradingView.
    Uses the consolidated TradingView streamer for network logic.
    Caches data in OCI Object Storage and locally in Parquet format.
    """

    def __init__(self, fs: any, bucket: str, cache_dir: str = "data"):
        super().__init__(fs, bucket, cache_dir, provider_name="tv")
        self._tv = TradingView()

    def get_history(self, symbol: str) -> np.ndarray:
        """Retrieves historical data for a symbol from the local cache."""
        if not self.cache_file_local.exists():
            self._sync_from_oci()

        if not self.cache_file_local.exists():
            return np.empty(0, dtype=CANDLE_DTYPE)

        try:
            df = pd.read_parquet(
                self.cache_file_local, filters=[("symbol", "==", symbol)]
            )
            if df.empty:
                return np.empty(0, dtype=CANDLE_DTYPE)

            history = np.zeros(len(df), dtype=CANDLE_DTYPE)
            history["timestamp"] = (
                df["timestamp"].values.astype("datetime64[s]").astype("int64")
            )
            history["open"] = df["open"].values
            history["high"] = df["high"].values
            history["low"] = df["low"].values
            history["close"] = df["close"].values
            history["volume"] = df["volume"].values
            return history
        except Exception as e:
            logger.error(f"Error reading cache for {symbol}: {e}")
            return np.empty(0, dtype=CANDLE_DTYPE)

    def _sync_from_oci(self):
        try:
            if self.fs.exists(self.cache_file_oci):
                self.fs.get(self.cache_file_oci, str(self.cache_file_local))
                logger.info(f"Synced cache from OCI: {self.cache_file_oci}")
        except Exception as e:
            logger.error(f"Failed to sync from OCI: {e}")

    async def refresh_cache(self, symbols: List[str]):
        logger.info(f"Refreshing TV cache for {len(symbols)} symbols...")
        dfs = []

        async for quotes, bars in self._tv.streamer.fetch_bulk(symbols, mode="bar"):
            for ticker, bar_list in bars.items():
                df = self._process_bars(bar_list)
                df["symbol"] = ticker
                dfs.append(df.reset_index())

        if not dfs:
            logger.warning("No data fetched from TradingView.")
            return

        full_df = pd.concat(dfs, ignore_index=True)
        full_df.to_parquet(self.cache_file_local, index=False)

        try:
            self.fs.put(str(self.cache_file_local), self.cache_file_oci)
            logger.info(f"Saved cache to OCI: {self.cache_file_oci}")
        except Exception as e:
            logger.error(f"Failed to save to OCI: {e}")

    def _process_bars(self, bar_data: List) -> pd.DataFrame:
        cols = ["timestamp", "open", "high", "low", "close", "volume"]
        df = pd.DataFrame(bar_data)
        df.columns = cols[: df.shape[1]]
        for col in cols:
            if col not in df.columns:
                df[col] = np.nan
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s").dt.floor("D")
        return df.set_index("timestamp")

    async def fetch_realtime(
        self, markets: List[str] = ["india", "america"]
    ) -> List[dict]:
        """
        Fetches latest OHLC data via scanner polling.
        """
        return await self._tv.scanner.fetch_ohlc(markets=markets)
