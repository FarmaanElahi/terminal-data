import asyncio
import logging
import os
import pickle
from typing import Dict, Optional, List, Literal

import pandas as pd
from fsspec.spec import AbstractFileSystem

from modules.core.provider.tradingview.tradingview import TradingView
from modules.ezscan.interfaces.candle_provider import CandleProvider

logger = logging.getLogger(__name__)


class TradingViewCandleProvider(CandleProvider):
    """Yahoo Finance candle provider."""

    def __init__(self,
                 fs: AbstractFileSystem,
                 market: Literal["india", "us"],
                 cache_file: Optional[str] = None,
                 period: str = "10y",

                 ):
        if cache_file is None:
            cache_file = f"ohlcv_{market}.pkl"
        self.fs = fs
        self.cache_file = cache_file
        self.cache_file_location = os.path.join(
            os.environ.get("BASE_FILE_PATH") if os.environ.get("BASE_FILE_PATH") else os.getcwd(),
            cache_file
        )
        self.period = period
        self.market = market
        self.symbol_data: Dict[str, pd.DataFrame] = {}
        self.base_symbols: List[str] = []
        self._load_symbols()

    def _load_symbols(self) -> None:
        """Load base symbols based on market."""
        try:
            if self.market == "india":
                self.base_symbols = TradingView.get_india_symbols_list()
            elif self.market == "us":
                self.base_symbols = TradingView.get_us_symbols_list()
        except Exception as e:
            logger.warning(f"Could not load symbols for {self.market}: {e}", exc_info=True)
            self.base_symbols = []

    def load_data(self) -> Dict[str, pd.DataFrame]:
        """Load OHLCV data."""
        if self._load_from_cache():
            return self.symbol_data
        return self._download_and_cache_data()

    def _load_from_cache(self) -> bool:
        """Attempt to load data from cache."""
        if not self.fs.exists(self.cache_file_location):
            return False
        try:
            with self.fs.open(self.cache_file_location, 'rb') as f:
                self.symbol_data = pickle.load(f)
            logger.info(f"Loaded {len(self.symbol_data)} symbol datasets from cache for {self.market}")
            return True
        except Exception as e:
            logger.error(f"Error loading cache for {self.market}: {e}", exc_info=True)
            return False

    async def _download_and_cache_data_async(self) -> Dict[str, pd.DataFrame]:
        data: dict[str, pd.DataFrame] = {}
        total = len(self.base_symbols)
        completed = 0
        async for symbol, candle in TradingView.stream_candles(self.base_symbols):
            data[symbol] = candle
            completed += 1
            if completed % 10 == 0:
                logger.info(f"Downloaded {completed}/{total} symbols for {self.market}")
        logger.info(f"Downloaded complete")
        return data

    def _download_and_cache_data(self) -> Dict[str, pd.DataFrame]:
        try:
            self.symbol_data = asyncio.run(self._download_and_cache_data_async())
            self._save_to_cache()
        except Exception as e:
            logger.error(f"Error downloading for {self.market}: {e}", exc_info=True)
            return {}
        return self.symbol_data

    def _save_to_cache(self) -> None:
        """Save data to cache."""
        try:
            with self.fs.open(self.cache_file_location, 'wb') as f:
                pickle.dump(self.symbol_data, f)
            logger.info(f"Cached data for {len(self.symbol_data)} symbols in {self.market}")
        except Exception as e:
            logger.error(f"Error saving cache for {self.market}: {e}", exc_info=True)

    def get_symbol_data(self, symbol: str) -> Optional[pd.DataFrame]:
        """Get symbol data."""
        return self.symbol_data.get(symbol)

    def get_available_symbols(self) -> List[str]:
        """Get available symbols."""
        return list(self.symbol_data.keys())

    def refresh_data(self) -> Dict[str, pd.DataFrame]:
        """Refresh data."""
        logger.info(f"Refreshing data from Yahoo Finance for {self.market}...")
        return self._download_and_cache_data()
