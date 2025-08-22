"""
Main application entry point.

This file demonstrates how to wire up the modular components
with dependency injection for maximum flexibility.
"""

import logging
import os
from fastapi import FastAPI
import uvicorn

from modules.ezscan.providers.yahoo_candle_provider import YahooCandleProvider
from modules.ezscan.providers.hardcoded_metadata_provider import HardcodedMetadataProvider
from modules.ezscan.core.scanner_engine import ScannerEngine
from modules.ezscan.api.routes import create_scanner_routes

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
MAX_WORKERS = min(32, (os.cpu_count() or 1) + 4)


def create_application() -> FastAPI:
    """
    Create and configure the FastAPI application.

    This function demonstrates dependency injection - you can easily
    swap out providers for different data sources or implementations.

    Returns:
        FastAPI: Configured application
    """
    # Initialize data providers
    candle_provider = YahooCandleProvider(
        cache_file="ohlcv_separated.pkl",
        period="10y"
    )

    metadata_provider = HardcodedMetadataProvider()

    # Initialize scanner engine with providers
    scanner_engine = ScannerEngine(
        candle_provider=candle_provider,
        metadata_provider=metadata_provider,
        max_workers=MAX_WORKERS
    )

    # Create FastAPI app
    app = FastAPI(
        title="Modular Stock Scanner API",
        description="Production-quality technical analysis scanner with pluggable data providers",
        version="2.0.0"
    )

    # Create and include routes
    scanner_router = create_scanner_routes(scanner_engine)
    app.include_router(scanner_router, prefix="/v1")

    return app


def main():
    """Main entry point."""
    logger.info("🚀 Starting Modular Stock Scanner API...")

    app = create_application()

    logger.info(f"⚡ Using {MAX_WORKERS} parallel workers")
    logger.info("🔧 Components initialized successfully")

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )


if __name__ == "__main__":
    main()
