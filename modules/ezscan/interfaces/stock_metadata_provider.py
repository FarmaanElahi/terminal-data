from abc import ABC, abstractmethod
from typing import Optional, Dict, Any


class StockMetadataProvider(ABC):
    """
    Abstract base class for providing stock-specific metadata.

    This interface provides fundamental data like EPS, revenue, debt, etc.
    that are not derived from price/volume but are company-specific metrics.
    """

    @abstractmethod
    def get_metadata(self, symbol: str, property_name: str) -> Optional[float]:
        """
        Get a specific metadata property for a symbol.

        Args:
            symbol: The symbol identifier (e.g., 'NSE:RELIANCE')
            property_name: The property to retrieve (e.g., 'eps', 'revenue', 'debt')

        Returns:
            Optional[float]: The property value, or None if not available.
        """
        pass

    @abstractmethod
    def get_all_metadata(self, symbol: str) -> Dict[str, Any]:
        """
        Get all available metadata for a symbol.

        Args:
            symbol: The symbol identifier

        Returns:
            Dict[str, Any]: Dictionary of all available metadata properties.
        """
        pass

    @abstractmethod
    def get_supported_properties(self) -> list[str]:
        """
        Get list of all supported metadata properties.

        Returns:
            list[str]: List of supported property names.
        """
        pass
