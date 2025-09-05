from abc import ABC, abstractmethod
from typing import Dict, Optional, List
import pandas as pd


class CandleProvider(ABC):
    """Abstract base class for OHLCV candle data providers."""

    @abstractmethod
    def load_data(self) -> Dict[str, pd.DataFrame]:
        """Load OHLCV data for all symbols."""
        pass

    @abstractmethod
    def get_symbol_data(self, symbol: str) -> Optional[pd.DataFrame]:
        """Get OHLCV data for a specific symbol."""
        pass

    @abstractmethod
    def get_available_symbols(self) -> List[str]:
        """Get list of all available symbols."""
        pass

    @abstractmethod
    def refresh_data(self) -> Dict[str, pd.DataFrame]:
        """Refresh data from the source."""
        pass