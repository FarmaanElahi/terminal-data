import logging
from typing import Optional, Dict, Any, List

import pandas as pd

from modules.ezscan.interfaces.metadata_provider import MetadataProvider

logger = logging.getLogger(__name__)


class LocalMetadataProvider(MetadataProvider):
    """
    Metadata provider that loads data from the symbols-full-v2.parquet file.

    This provider loads real fundamental and technical data from the production
    parquet file stored in Oracle Cloud Storage.
    """

    def __init__(self):
        """Initialize by loading the metadata DataFrame from parquet file."""
        self._metadata_df = None
        self._load_metadata()

    def _load_metadata(self):
        """Load metadata from the parquet file."""
        try:
            url = "https://objectstorage.ap-hyderabad-1.oraclecloud.com/n/axbaetdfzydd/b/terminal-files/o/symbols-full-v2.parquet"
            self._metadata_df = pd.read_parquet(url)
            logger.info(f"Loaded metadata for {len(self._metadata_df)} symbols with {len(self._metadata_df.columns)} properties")
        except Exception as e:
            logger.error(f"Failed to load metadata from parquet file: {e}")
            # Create empty DataFrame as fallback
            self._metadata_df = pd.DataFrame()

    def get_metadata(self, symbol: str, property_name: str) -> Optional[float]:
        """
        Get a specific metadata property for a symbol.

        Args:
            symbol: Symbol identifier
            property_name: Property name to retrieve

        Returns:
            Optional[float]: Property value or None if not available
        """
        if self._metadata_df is None or self._metadata_df.empty:
            return None

        if symbol not in self._metadata_df.index:
            logger.debug(f"Symbol '{symbol}' not found in metadata")
            return None

        if property_name not in self._metadata_df.columns:
            logger.debug(f"Property '{property_name}' not found in metadata")
            return None

        try:
            value = self._metadata_df.loc[symbol, property_name]
            if pd.isna(value):
                return None
            return float(value) if pd.api.types.is_numeric_dtype(self._metadata_df[property_name]) else value
        except Exception as e:
            logger.debug(f"Error retrieving {property_name} for {symbol}: {e}")
            return None

    def get_all_metadata(self, symbol: str) -> Dict[str, Any]:
        """
        Get all available metadata for a symbol.

        Args:
            symbol: Symbol identifier

        Returns:
            Dict[str, Any]: Dictionary of all available metadata properties
        """
        if self._metadata_df is None or self._metadata_df.empty:
            return {}

        if symbol not in self._metadata_df.index:
            logger.debug(f"Symbol '{symbol}' not found in metadata")
            return {}

        try:
            symbol_data = self._metadata_df.loc[symbol].to_dict()
            # Remove NaN values
            return {k: v for k, v in symbol_data.items() if not pd.isna(v)}
        except Exception as e:
            logger.debug(f"Error retrieving all metadata for {symbol}: {e}")
            return {}

    def get_supported_properties(self) -> list[str]:
        """
        Get list of all supported metadata properties.

        Returns:
            list[str]: List of supported property names
        """
        if self._metadata_df is None or self._metadata_df.empty:
            return []

        return self._metadata_df.columns.tolist()

    def get_metadata_dataframe(self, symbols: List[str] = None) -> pd.DataFrame:
        """
        Get metadata for symbols as a DataFrame for vectorized operations.

        Args:
            symbols: Optional list of symbols to filter by. If None, returns all symbols.

        Returns:
            pd.DataFrame: DataFrame with symbols as index and metadata properties as columns
        """
        if self._metadata_df is None or self._metadata_df.empty:
            logger.warning("No metadata available")
            return pd.DataFrame()

        if symbols is None:
            return self._metadata_df.copy()

        # Filter to requested symbols that exist in the data
        available_symbols = [s for s in symbols if s in self._metadata_df.index]

        if not available_symbols:
            logger.warning(f"None of the requested symbols found in metadata")
            return pd.DataFrame()

        return self._metadata_df.loc[available_symbols].copy()

    def refresh_metadata(self):
        """Refresh metadata by reloading from the parquet file."""
        logger.info("Refreshing metadata from parquet file...")
        self._load_metadata()

    def get_available_symbols(self) -> List[str]:
        """
        Get list of all available symbols in the metadata.

        Returns:
            List[str]: List of available symbol identifiers
        """
        if self._metadata_df is None or self._metadata_df.empty:
            return []

        return self._metadata_df.index.tolist()

    def get_symbol_count(self) -> int:
        """
        Get the total number of symbols in the metadata.

        Returns:
            int: Number of symbols
        """
        if self._metadata_df is None or self._metadata_df.empty:
            return 0

        return len(self._metadata_df)

    def get_property_count(self) -> int:
        """
        Get the total number of properties in the metadata.

        Returns:
            int: Number of properties
        """
        if self._metadata_df is None or self._metadata_df.empty:
            return 0

        return len(self._metadata_df.columns)

    def get_metadata_info(self) -> Dict[str, Any]:
        """
        Get information about the metadata dataset.

        Returns:
            Dict[str, Any]: Information about the dataset
        """
        if self._metadata_df is None or self._metadata_df.empty:
            return {
                "status": "empty",
                "symbol_count": 0,
                "property_count": 0,
                "properties": []
            }

        return {
            "status": "loaded",
            "symbol_count": len(self._metadata_df),
            "property_count": len(self._metadata_df.columns),
            "properties": self._metadata_df.columns.tolist(),
            "memory_usage": f"{self._metadata_df.memory_usage(deep=True).sum() / 1024 / 1024:.2f} MB"
        }
