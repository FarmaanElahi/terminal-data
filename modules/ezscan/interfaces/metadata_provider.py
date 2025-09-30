from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
import pandas as pd


class MetadataProvider(ABC):
    """Abstract base class for stock metadata providers."""

    @abstractmethod
    def load(self):
        pass

    @abstractmethod
    def get_metadata(self, symbol: str, property_name: str) -> Optional[float]:
        """Get a specific metadata property for a symbol."""
        pass

    @abstractmethod
    def get_all_metadata(self, symbol: str) -> Dict[str, Any]:
        """Get all available metadata for a symbol."""
        pass

    @abstractmethod
    def get_supported_properties(self) -> List[str]:
        """Get list of supported metadata properties."""
        pass

    @abstractmethod
    def get_metadata_dataframe(self, symbols: Optional[List[str]] = None) -> pd.DataFrame:
        """Get metadata as a DataFrame for vectorized operations."""
        pass
