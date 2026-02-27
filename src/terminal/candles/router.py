"""FastAPI router for the candles module.

Provides REST endpoints for fetching historical and intraday candle data.
Accepts terminal-format tickers (``NSE:RELIANCE``) and resolves them to
provider-specific instrument keys via the symbols service.

Interval is a free-form string — Upstox V3 accepts any valid unit/num combo.
"""

import logging
from datetime import date

from fastapi import APIRouter, Depends, Query

from terminal.candles.models import CandleResponse
from terminal.candles.service import CandleManager
from terminal.dependencies import get_candle_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/candles", tags=["Candles"])


@router.get("/{ticker:path}/historical", response_model=CandleResponse)
async def get_historical_candles(
    ticker: str,
    interval: str = Query(
        "1D",
        description="Candle interval (e.g. '1', '5', '15', '60', '1D', '1W', '1M')",
    ),
    from_date: date | None = Query(None, description="Start date (YYYY-MM-DD)"),
    to_date: date | None = Query(None, description="End date (YYYY-MM-DD)"),
    manager: CandleManager = Depends(get_candle_manager),
):
    """Fetch historical candle data for a symbol.

    Interval is a TradingView-compatible resolution string:
      - Minutes: "1", "3", "5", "15", "30"
      - Hours:   "60", "120", "240"
      - Daily:   "1D"
      - Weekly:  "1W"
      - Monthly: "1M", "3M", "6M"

    Example: ``GET /candles/NSE:RELIANCE/historical?interval=1D&from_date=2025-01-01``
    """
    candles = await manager.get_candles(
        ticker=ticker,
        interval=interval,
        from_date=from_date,
        to_date=to_date,
    )

    return CandleResponse(
        ticker=ticker,
        interval=interval,
        candles=candles,
    )


@router.get("/{ticker:path}/intraday", response_model=CandleResponse)
async def get_intraday_candles(
    ticker: str,
    interval: str = Query(
        "1", description="Intraday interval (e.g. '1', '5', '15', '60')"
    ),
    manager: CandleManager = Depends(get_candle_manager),
):
    """Fetch today's intraday candle data for a symbol.

    Uses the Upstox intraday endpoint which returns current session candles.
    Interval should be a minute or hour based resolution.

    Example: ``GET /candles/NSE:RELIANCE/intraday?interval=5``
    """
    candles = await manager.get_candles(
        ticker=ticker,
        interval=interval,
        # No dates → defaults to today (intraday only)
    )

    return CandleResponse(
        ticker=ticker,
        interval=interval,
        candles=candles,
    )
