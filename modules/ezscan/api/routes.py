"""
FastAPI routes for the scanner API.
"""

import logging
from fastapi import APIRouter, HTTPException

from modules.ezscan.core.scanner_engine import ScannerEngine
from modules.ezscan.models.requests import ScanRequest
from modules.ezscan.models.responses import ScanResponse

logger = logging.getLogger(__name__)


def create_scanner_routes(scanner_engine: ScannerEngine) -> APIRouter:
    """
    Create API routes with injected scanner engine.

    Args:
        scanner_engine: Configured scanner engine instance

    Returns:
        APIRouter: Configured router with all endpoints
    """
    router = APIRouter()

    @router.get("/")
    def health():
        """Health check endpoint."""
        stats = scanner_engine.get_cache_stats()
        return {
            "status": "ok",
            "symbols": stats["loaded_symbols"],
            "cache_hits": stats["cache_hits"],
            "cache_misses": stats["cache_misses"],
            "version": "modular_v2"
        }

    @router.get("/symbols")
    def get_symbols():
        """Get all available symbols."""
        symbols = scanner_engine.get_available_symbols()
        return {"symbols": symbols, "count": len(symbols)}

    @router.post("/scan", response_model=ScanResponse)
    def scan(request: ScanRequest):
        """Execute technical scan."""
        try:
            result = scanner_engine.scan(
                conditions=request.conditions,
                columns=request.columns,
                logic=request.logic,
                sort_columns=request.sort_columns
            )
            return result
        except Exception as e:
            logger.error(f"Scan failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/symbol/{symbol}")
    def get_symbol_data(symbol: str):
        """Get data for a specific symbol."""
        try:
            return scanner_engine.get_symbol_info(symbol)
        except Exception as e:
            logger.error(f"Failed to get symbol data for {symbol}: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/cache-stats")
    def get_cache_stats():
        """Get cache performance statistics."""
        return scanner_engine.get_cache_stats()

    @router.post("/clear-cache")
    def clear_cache():
        """Clear expression cache."""
        scanner_engine.clear_cache()
        return {"status": "cache_cleared"}

    @router.post("/refresh-data")
    def refresh_data():
        """Refresh data from providers."""
        scanner_engine.refresh_data()
        return {"status": "data_refreshed"}

    return router
