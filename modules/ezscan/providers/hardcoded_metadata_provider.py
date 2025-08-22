from typing import Optional, Dict, Any
import logging

from modules.ezscan.interfaces.stock_metadata_provider import StockMetadataProvider

logger = logging.getLogger(__name__)


class HardcodedMetadataProvider(StockMetadataProvider):
    """
    Hardcoded implementation of StockMetadataProvider.

    This is a simple implementation that returns hardcoded values.
    In production, this would be replaced with a provider that fetches
    real fundamental data from sources like financial APIs.
    """

    def __init__(self):
        """Initialize with hardcoded metadata values."""
        self.default_values = {
            "eps": 50.0,
            "opm": 20.0,  # Operating Profit Margin
            "pat": 10.0,  # Profit After Tax
            "revenue": 100.0,
            "debt": 5.0,
            "market_cap": 1000.0,
            "pe_ratio": 15.0,
            "pb_ratio": 2.5,
            "roe": 18.0,  # Return on Equity
            "roa": 12.0,  # Return on Assets
        }

    def get_metadata(self, symbol: str, property_name: str) -> Optional[float]:
        """
        Get a specific metadata property for a symbol.

        Args:
            symbol: Symbol identifier
            property_name: Property name to retrieve

        Returns:
            Optional[float]: Property value or None if not supported
        """
        if property_name not in self.default_values:
            logger.warning(f"Property '{property_name}' not supported")
            return None

        # In a real implementation, this would vary by symbol
        # For now, return the same value for all symbols
        return self.default_values[property_name]

    def get_all_metadata(self, symbol: str) -> Dict[str, Any]:
        """
        Get all available metadata for a symbol.

        Args:
            symbol: Symbol identifier

        Returns:
            Dict[str, Any]: All available metadata
        """
        # In a real implementation, this would be symbol-specific
        return self.default_values.copy()

    def get_supported_properties(self) -> list[str]:
        """
        Get list of supported metadata properties.

        Returns:
            list[str]: List of supported property names
        """
        return list(self.default_values.keys())
