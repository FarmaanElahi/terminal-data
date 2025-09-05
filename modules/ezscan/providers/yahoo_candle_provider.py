import logging
import os
import pickle
from typing import Dict, Optional, List
import pandas as pd
import yfinance as yf
from modules.ezscan.interfaces.candle_provider import CandleProvider
from modules.core.provider.tradingview.tradingview import TradingView

logger = logging.getLogger(__name__)


class YahooCandleProvider(CandleProvider):
    """Yahoo Finance candle provider."""

    def __init__(self, cache_file: str = "ohlcv_separated.pkl", period: str = "10y"):
        self.cache_file = cache_file
        self.period = period
        self.symbol_data: Dict[str, pd.DataFrame] = {}
        self.base_symbols: List[str] = []
        self._load_symbols()

    def _load_symbols(self) -> None:
        """Load base symbols."""
        try:
            self.base_symbols = TradingView.get_base_symbols().index.tolist()
        except Exception as e:
            logger.warning(f"Could not load TradingView symbols: {e}", exc_info=True)
            self.base_symbols = []

    def load_data(self) -> Dict[str, pd.DataFrame]:
        """Load OHLCV data."""
        if self._load_from_cache():
            return self.symbol_data
        return self._download_and_cache_data()

    def _load_from_cache(self) -> bool:
        """Attempt to load data from cache."""
        if not os.path.exists(self.cache_file):
            return False
        try:
            with open(self.cache_file, 'rb') as f:
                self.symbol_data = pickle.load(f)
            logger.info(f"Loaded {len(self.symbol_data)} symbol datasets from cache")
            return True
        except Exception as e:
            logger.error(f"Error loading cache: {e}", exc_info=True)
            return False

    def _download_and_cache_data(self) -> Dict[str, pd.DataFrame]:
        """Download and cache data."""
        logger.info("Downloading OHLCV data from Yahoo Finance...")
        if not self.base_symbols:
            logger.warning("No symbols available for download")
            return {}

        yf_symbols = [s.split(":")[1] + ".NS" for s in self.base_symbols]
        try:
            df = yf.download(yf_symbols, period=self.period, interval="1d", group_by="ticker", auto_adjust=True)
            self.symbol_data = self._process_downloaded_data(df, yf_symbols)
            self._save_to_cache()
        except Exception as e:
            logger.error(f"Error downloading: {e}", exc_info=True)
            return {}
        return self.symbol_data

    def _process_downloaded_data(self, df: pd.DataFrame, yf_symbols: List[str]) -> Dict[str, pd.DataFrame]:
        """Process downloaded data."""
        processed_data = {}
        for i, sym in enumerate(yf_symbols):
            if sym not in df:
                logger.warning(f"Skipping missing symbol {sym}")
                continue
            try:
                sdf = df[sym].copy()
                if sdf.empty:
                    continue
                sdf.columns = [c.lower() for c in sdf.columns]
                sdf = sdf.dropna().sort_index()
                processed_data["NSE:" + sym.split(".")[0]] = sdf
                if (i + 1) % 100 == 0:
                    logger.info(f"Processed {i + 1}/{len(yf_symbols)} symbols")
            except Exception as e:
                logger.warning(f"Error processing {sym}: {e}")
                continue
        logger.info(f"Successfully processed {len(processed_data)} symbols")
        return processed_data

    def _save_to_cache(self) -> None:
        """Save data to cache."""
        try:
            with open(self.cache_file, 'wb') as f:
                pickle.dump(self.symbol_data, f)
            logger.info(f"Cached data for {len(self.symbol_data)} symbols")
        except Exception as e:
            logger.error(f"Error saving cache: {e}", exc_info=True)

    def get_symbol_data(self, symbol: str) -> Optional[pd.DataFrame]:
        """Get symbol data."""
        return self.symbol_data.get(symbol)

    def get_available_symbols(self) -> List[str]:
        """Get available symbols."""
        return list(self.symbol_data.keys())

    def refresh_data(self) -> Dict[str, pd.DataFrame]:
        """Refresh data."""
        logger.info("Refreshing data from Yahoo Finance...")
        self.symbol_data.clear()
        return self._download_and_cache_data()
