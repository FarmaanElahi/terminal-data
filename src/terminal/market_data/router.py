from fastapi import APIRouter, Depends, HTTPException, Query
from terminal.market_data.manager import MarketDataManager
from terminal.dependencies import get_market_manager

router = APIRouter(prefix="/market-data", tags=["Market Data"])


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
