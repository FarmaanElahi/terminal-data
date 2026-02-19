from fastapi import APIRouter, Depends, HTTPException, Query
from terminal.market_feed.manager import MarketDataManager
from terminal.dependencies import (
    get_market_manager,
    get_session,
    get_tradingview_provider,
)
from terminal.market_feed.models import MarketFeedRefreshResponse
from terminal.symbols import service as symbol_service
from terminal.market_feed.tradingview import TradingViewDataProvider
from sqlalchemy.orm import Session

router = APIRouter(prefix="/market-feed", tags=["Market Feed"])


@router.get("/{symbol}")
async def get_ohlcv(
    symbol: str,
    refresh: bool = Query(
        False, description="If true, fetches latest history from source"
    ),
    manager: MarketDataManager = Depends(get_market_manager),
):
    """
    Retrieve OHLCV data for a given symbol in columnar format.
    Example symbol: 'NSE:RELIANCE', 'NASDAQ:AAPL'
    """
    if refresh:
        await manager.load_history([symbol])

    data = manager.get_ohlcv_series(symbol)

    if data is None:
        # If no data and we didn't just refresh, try a quick refresh
        if not refresh:
            await manager.load_history([symbol])
            data = manager.get_ohlcv_series(symbol)

        if data is None:
            raise HTTPException(
                status_code=404, detail=f"No data found for symbol: {symbol}"
            )

    return {"data": data}


@router.post("/refresh", response_model=MarketFeedRefreshResponse)
async def refresh_market_feed(
    market: str = Query("india", description="Market to refresh symbols for"),
    provider: TradingViewDataProvider = Depends(get_tradingview_provider),
    session: Session = Depends(get_session),
):
    """
    Trigger a refresh of the market feed candles from TradingView.
    This mirrors the 'market-data refresh-daily' CLI command.
    """

    try:
        # Fetch symbols from database
        symbols_info = await symbol_service.search(session, market=market, limit=20000)
        tickers = [s.ticker for s in symbols_info]

        if not tickers:
            return MarketFeedRefreshResponse(
                status="success",
                count=0,
                message=f"No symbols found for market: {market}",
            )

        # Trigger refresh
        await provider.refresh_cache(tickers)

        return MarketFeedRefreshResponse(
            status="success",
            count=len(tickers),
            message=f"Successfully refreshed candles for {len(tickers)} symbols.",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
