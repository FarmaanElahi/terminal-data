import logging
import os
import pickle
from typing import Dict, Optional
import pandas as pd
import yfinance as yf

from modules.ezscan.interfaces.candle_provider import CandleProvider
from modules.core.provider.tradingview.tradingview import TradingView

logger = logging.getLogger(__name__)


class YahooCandleProvider(CandleProvider):
    """
    Yahoo Finance implementation of CandleProvider.

    Provides OHLCV data from Yahoo Finance with local caching
    for improved performance.
    """

    def __init__(self, cache_file: str = "ohlcv_separated.pkl", period: str = "10y"):
        """
        Initialize Yahoo Finance candle provider.

        Args:
            cache_file: Path to cache file for storing downloaded data
            period: Period for historical data (e.g., '10y', '5y', '1y')
        """
        self.cache_file = cache_file
        self.period = period
        self.symbol_data: Dict[str, pd.DataFrame] = {}
        self._load_symbols()

    def _load_symbols(self) -> None:
        """Load base symbols from TradingView."""
        try:
            self.base_symbols = TradingView.get_base_symbols().index.tolist()
        except Exception as e:
            logger.warning(f"Could not load TradingView symbols: {e}")
            self.base_symbols = []

    def load_data(self) -> Dict[str, pd.DataFrame]:
        """
        Load OHLCV data from cache or download from Yahoo Finance.

        Returns:
            Dict[str, pd.DataFrame]: Dictionary of symbol data
        """
        if self._load_from_cache():
            return self.symbol_data

        return self._download_and_cache_data()

    def _load_from_cache(self) -> bool:
        """
        Attempt to load data from cache file.

        Returns:
            bool: True if successfully loaded from cache, False otherwise
        """
        if not os.path.exists(self.cache_file):
            return False

        try:
            logger.info("Loading cached OHLCV data...")
            with open(self.cache_file, 'rb') as f:
                self.symbol_data = pickle.load(f)
            logger.info(f"Loaded {len(self.symbol_data)} symbol datasets from cache")
            return True
        except Exception as e:
            logger.error(f"Error loading cache: {e}")
            return False

    def _download_and_cache_data(self) -> Dict[str, pd.DataFrame]:
        """
        Download data from Yahoo Finance and cache it.

        Returns:
            Dict[str, pd.DataFrame]: Dictionary of symbol data
        """
        logger.info("Downloading OHLCV data from Yahoo Finance...")

        if not self.base_symbols:
            logger.warning("No symbols available for download")
            return {}

        # Convert to Yahoo Finance format
        yf_symbols = [s.split(":")[1] + ".NS" for s in self.base_symbols]

        try:
            df = yf.download(
                yf_symbols,
                period=self.period,
                interval="1d",
                group_by="ticker",
                auto_adjust=True
            )

            self.symbol_data = self._process_downloaded_data(df, yf_symbols)
            self._save_to_cache()

        except Exception as e:
            logger.error(f"Error downloading  {e}")
            return {}

        return self.symbol_data

    def _process_downloaded_data(self, df: pd.DataFrame, yf_symbols: list[str]) -> Dict[str, pd.DataFrame]:
        """
        Process and clean downloaded data.

        Args:
            df: Raw downloaded DataFrame from yfinance
            yf_symbols: List of Yahoo Finance symbol identifiers

        Returns:
            Dict[str, pd.DataFrame]: Processed symbol data
        """
        processed_data = {}

        for i, sym in enumerate(yf_symbols):
            if sym not in df:
                logger.warning(f"Skipping missing symbol {sym}")
                continue

            try:
                sdf = df[sym].copy()
                if sdf.empty:
                    continue

                # Clean and prepare data
                sdf.columns = [c.lower() for c in sdf.columns]
                sdf = sdf.dropna()

                if len(sdf) < 20:  # Skip symbols with insufficient data
                    continue

                # Sort by date for efficient operations
                sdf = sdf.sort_index()

                # Convert back to NSE format
                nse_symbol = "NSE:" + sym.split(".")[0]
                processed_data[nse_symbol] = sdf

                if (i + 1) % 100 == 0:
                    logger.info(f"Processed {i + 1}/{len(yf_symbols)} symbols")

            except Exception as e:
                logger.warning(f"Error processing {sym}: {e}")
                continue

        logger.info(f"Successfully processed {len(processed_data)} symbols")
        return processed_data

    def _save_to_cache(self) -> None:
        """Save processed data to cache file."""
        try:
            with open(self.cache_file, 'wb') as f:
                pickle.dump(self.symbol_data, f)
            logger.info(f"Cached data for {len(self.symbol_data)} symbols")
        except Exception as e:
            logger.error(f"Error saving cache: {e}")

    def get_symbol_data(self, symbol: str) -> Optional[pd.DataFrame]:
        """
        Get OHLCV data for a specific symbol.

        Args:
            symbol: Symbol identifier (e.g., 'NSE:RELIANCE')

        Returns:
            Optional[pd.DataFrame]: OHLCV data or None if not found
        """
        return self.symbol_data.get(symbol)

    def get_available_symbols(self) -> list[str]:
        """
        Get list of all available symbols.

        Returns:
            list[str]: List of available symbol identifiers
        """
        return list(self.symbol_data.keys())

    def refresh_data(self) -> None:
        """Refresh data by re-downloading from Yahoo Finance."""
        logger.info("Refreshing data from Yahoo Finance...")
        self.symbol_data.clear()
        self._download_and_cache_data()
