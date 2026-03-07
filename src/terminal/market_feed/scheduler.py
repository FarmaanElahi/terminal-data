"""APScheduler-based candle data refresh scheduler.

Schedules daily bar downloads per exchange after their market close time.
Tracks job execution status in OCI Object Storage as JSON files.
"""

import asyncio
import logging
import json
from datetime import datetime, timezone
from typing import Any

from terminal.dependencies import get_fs, get_settings

logger = logging.getLogger(__name__)

# Timeframes to refresh per schedule run
REFRESH_TIMEFRAMES = ["1D"]


def get_remote_status_path(exchange: str, timeframe: str) -> str:
    """Get the OCI path for the status JSON file."""
    settings = get_settings()
    return f"{settings.oci_bucket}/status/{exchange}_{timeframe}.json"


async def save_remote_status(exchange: str, timeframe: str, data: dict) -> None:
    """Save the refresh status to a JSON file in OCI storage."""
    fs = get_fs()
    path = get_remote_status_path(exchange, timeframe)
    try:
        with fs.open(path, "w") as f:
            json.dump(data, f)
        logger.debug("Saved remote status to %s", path)
    except Exception as e:
        logger.error("Failed to save remote status to %s: %s", path, e)


async def load_remote_status(exchange: str, timeframe: str) -> dict | None:
    """Load the latest refresh status from its JSON file in OCI."""
    fs = get_fs()
    path = get_remote_status_path(exchange, timeframe)
    try:
        if fs.exists(path):
            with fs.open(path, "r") as f:
                return json.load(f)
    except Exception as e:
        logger.error("Failed to load remote status from %s: %s", path, e)
    return None


async def run_candle_refresh(
    exchange: str, timeframe: str, bars: int = 1500
) -> dict[str, Any] | None:
    """Execute a single refresh job and record status in remote storage.

    Can be called by the scheduler or directly from the CLI.
    """
    status_data: dict[str, Any] = {
        "exchange": exchange,
        "timeframe": timeframe,
        "status": "running",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": None,
        "symbols_count": 0,
        "duration_seconds": 0.0,
        "error_message": None,
    }
    await save_remote_status(exchange, timeframe, status_data)

    start_time = asyncio.get_event_loop().time()

    try:
        logger.info(
            "Starting refresh for %s/%s (bars=%d)...",
            exchange,
            timeframe,
            bars,
        )

        from terminal.dependencies import (
            _get_tradingview_provider_instance,
            get_fs,
            get_settings,
        )
        from terminal.symbols import service as symbol_service

        provider = _get_tradingview_provider_instance()
        fs = get_fs()
        settings = get_settings()

        # Get symbols for this exchange
        await symbol_service.init(fs, settings)
        symbols_info = await symbol_service.search(
            fs=fs, settings=settings, limit=20000
        )
        tickers = [
            s["ticker"]
            for s in symbols_info
            if s["ticker"].split(":")[0] == exchange
        ]

        if not tickers:
            logger.warning("No symbols found for exchange %s", exchange)
            status_data.update(
                {"status": "success", "symbols_count": 0, "completed_at": datetime.now(timezone.utc).isoformat()}
            )
            await save_remote_status(exchange, timeframe, status_data)
            return status_data

        def on_progress(completed: int, total: int):
            if completed % 10 == 0 or completed == total:
                logger.info(
                    "Progress for %s/%s: %d/%d (%.1f%%)",
                    exchange,
                    timeframe,
                    completed,
                    total,
                    (completed / total) * 100,
                )

        # Download bars
        saved = await provider.download_bars_for_exchange(
            tickers, exchange, timeframe=timeframe, bars=bars, on_progress=on_progress
        )

        duration = asyncio.get_event_loop().time() - start_time
        logger.info(
            "Refresh complete for %s/%s: %d symbols in %.1fs",
            exchange,
            timeframe,
            saved,
            duration,
        )

        status_data.update(
            {
                "status": "success",
                "symbols_count": saved,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "duration_seconds": float(f"{duration:.2f}"),
            }
        )
        await save_remote_status(exchange, timeframe, status_data)

    except Exception as e:
        duration = asyncio.get_event_loop().time() - start_time
        logger.exception(
            "Refresh failed for %s/%s after %.1fs",
            exchange,
            timeframe,
            duration,
        )
        status_data.update(
            {
                "status": "failed",
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "duration_seconds": float(f"{duration:.2f}"),
                "error_message": str(e),
            }
        )
        await save_remote_status(exchange, timeframe, status_data)

    return status_data
