"""Health check endpoints for liveness and readiness probes."""

import logging
import time
from typing import Any

from fastapi import APIRouter, Response, status
from sqlalchemy import text

from terminal.database.core import engine
from terminal.dependencies import get_market_manager, get_candle_manager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Health"])


@router.get("/health")
async def liveness() -> dict[str, str]:
    """Liveness probe — returns 200 if the process is up."""
    return {"status": "ok"}


@router.get("/ready")
async def readiness(response: Response) -> dict[str, Any]:
    """Readiness probe — checks DB, MarketDataManager, and CandleManager.

    Returns 200 if all checks pass, 503 with details if any fail.
    """
    checks: dict[str, Any] = {}
    all_ok = True

    # 1. Database connectivity
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["database"] = {"status": "ok"}
    except Exception as e:
        checks["database"] = {"status": "error", "detail": str(e)}
        all_ok = False

    # 2. MarketDataManager status
    try:
        manager = await get_market_manager()
        md_status: dict[str, Any] = {"status": "ok"}

        if hasattr(manager, "_last_successful_poll") and manager._last_successful_poll:
            staleness = time.time() - manager._last_successful_poll
            md_status["last_poll_seconds_ago"] = round(staleness, 1)
            if staleness > 30:
                md_status["status"] = "degraded"
                md_status["detail"] = f"Last successful poll {staleness:.0f}s ago"

        if hasattr(manager, "_consecutive_failures"):
            md_status["consecutive_failures"] = manager._consecutive_failures

        checks["market_data"] = md_status
    except Exception as e:
        checks["market_data"] = {"status": "error", "detail": str(e)}
        all_ok = False

    # 3. CandleManager / feed status
    try:
        candle_manager = await get_candle_manager()
        feed_status: dict[str, Any] = {"status": "ok"}

        if not candle_manager.has_feed:
            feed_status["status"] = "unconfigured"
            feed_status["detail"] = "No real-time feed configured"

        checks["candle_feed"] = feed_status
    except Exception as e:
        checks["candle_feed"] = {"status": "error", "detail": str(e)}
        all_ok = False

    if not all_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {"status": "ok" if all_ok else "degraded", "checks": checks}
