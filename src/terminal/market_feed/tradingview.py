import logging
import pandas as pd
import numpy as np
from typing import List

from .provider import DataProvider

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

    async def refresh_cache(self, symbols: List[str]):
        logger.info(f"Refreshing TV cache for {len(symbols)} symbols...")
        dfs = []

        async for bar_dict in self._tv.streamer.stream_bars(symbols, timeframe="1D"):
            # Output is like: {"NSE:TCS": [{}, {}, ...]}
            for ticker, bar_list in bar_dict.items():
                df = self._process_bars(bar_list)
                df["symbol"] = ticker
                dfs.append(df.reset_index())

        if not dfs:
            logger.warning("No data fetched from TradingView.")
            return

        full_df = pd.concat(dfs, ignore_index=True)
        self.update_cache(full_df)

    def _process_bars(self, bar_data: List) -> pd.DataFrame:
        cols = ["timestamp", "open", "high", "low", "close", "volume"]
        df = pd.DataFrame(bar_data)
        df.columns = cols[: df.shape[1]]
        for col in cols:
            if col not in df.columns:
                df[col] = np.nan
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s").dt.floor("D")
        return df.set_index("timestamp")
