from abc import ABC, abstractmethod
from typing import Dict, Optional
import pandas as pd


class CandleProvider(ABC):
    """
    Abstract base class for providing OHLCV candle data.

    This interface allows the scanner to work with any data source
    (Yahoo Finance, Kite, Alpha Vantage, etc.) by implementing
    this common interface.
    """

    @abstractmethod
    def load_data(self) -> Dict[str, pd.DataFrame]:
        """
        Load and return OHLCV data for all symbols.

        Returns:
            Dict[str, pd.DataFrame]: Dictionary mapping symbol names to their OHLCV DataFrames.
                Each DataFrame should have columns: ['open', 'high', 'low', 'close', 'volume']
                with DatetimeIndex.
        """
        pass

    @abstractmethod
    def get_symbol_data(self, symbol: str) -> Optional[pd.DataFrame]:
        """
        Get OHLCV data for a specific symbol.

        Args:
            symbol: The symbol identifier (e.g., 'NSE:RELIANCE')

        Returns:
            Optional[pd.DataFrame]: OHLCV DataFrame for the symbol, or None if not found.
        """
        pass

    @abstractmethod
    def get_available_symbols(self) -> list[str]:
        """
        Get list of all available symbols.

        Returns:
            list[str]: List of available symbol identifiers.
        """
        pass

    @abstractmethod
    def refresh_data(self) -> dict[str,pd.DataFrame]:
        """
        Refresh/reload the data from the source.
        """
        pass
