import logging
from typing import Optional, Dict, Any, List
import pandas as pd

from modules.core.provider.tradingview.tradingview import TradingView
from modules.ezscan.interfaces.metadata_provider import MetadataProvider

logger = logging.getLogger(__name__)


class USMetadataProvider(MetadataProvider):
    """Placeholder metadata provider for US stocks."""

    def __init__(self):
        """Initialize placeholder."""
        self._load_metadata()

    def _load_metadata(self) -> None:
        """Load metadata from TradingView."""
        df = TradingView.get_us_symbols()
        self._metadata_df = df

    def get_metadata(self, symbol: str, property_name: str) -> Optional[float]:
        if self._metadata_df is None or self._metadata_df.empty:
            return None
        if symbol not in self._metadata_df.index or property_name not in self._metadata_df.columns:
            return None
        try:
            value = self._metadata_df.loc[symbol, property_name]
            return None if pd.isna(value) else float(value) if pd.api.types.is_numeric_dtype(self._metadata_df[property_name]) else value
        except Exception as e:
            logger.debug(f"Error retrieving {property_name} for {symbol}: {e}")
            return None

    def get_all_metadata(self, symbol: str) -> Dict[str, Any]:
        """Get all metadata for a symbol."""
        if self._metadata_df is None or self._metadata_df.empty or symbol not in self._metadata_df.index:
            return {}
        try:
            # Only include scalar values that are not NaN
            return {
                k: v for k, v in self._metadata_df.loc[symbol].to_dict().items()
                if pd.api.types.is_scalar(v) and not pd.isna(v)
            }
        except Exception as e:
            logger.debug(f"Error retrieving metadata for {symbol}: {e}")
            return {}

    def get_supported_properties(self) -> List[str]:
        """Get supported metadata properties."""
        return [] if self._metadata_df is None or self._metadata_df.empty else self._metadata_df.columns.tolist()

    def get_metadata_dataframe(self, symbols: Optional[List[str]] = None) -> pd.DataFrame:
        """Get metadata DataFrame."""
        if self._metadata_df is None or self._metadata_df.empty:
            return pd.DataFrame()
        if symbols is None:
            return self._metadata_df.copy()
        available_symbols = [s for s in symbols if s in self._metadata_df.index]
        return self._metadata_df.loc[available_symbols].copy() if available_symbols else pd.DataFrame()

    def refresh_metadata(self) -> None:
        """Refresh metadata."""
        logger.info("Refreshing metadata...")
        self._load_metadata()

    def get_available_symbols(self) -> List[str]:
        """Get available symbols."""
        return [] if self._metadata_df is None or self._metadata_df.empty else self._metadata_df.index.tolist()

    def get_symbol_count(self) -> int:
        """Get total number of symbols."""
        return 0 if self._metadata_df is None or self._metadata_df.empty else len(self._metadata_df)

    def get_property_count(self) -> int:
        """Get total number of properties."""
        return 0 if self._metadata_df is None or self._metadata_df.empty else len(self._metadata_df.columns)

    def get_metadata_info(self) -> Dict[str, Any]:
        """Get metadata dataset info."""
        if self._metadata_df is None or self._metadata_df.empty:
            return {"status": "empty", "symbol_count": 0, "property_count": 0, "properties": []}
        return {
            "status": "loaded",
            "symbol_count": len(self._metadata_df),
            "property_count": len(self._metadata_df.columns),
            "properties": self._metadata_df.columns.tolist(),
            "memory_usage": f"{self._metadata_df.memory_usage(deep=True).sum() / 1024 / 1024:.2f} MB"
        }
