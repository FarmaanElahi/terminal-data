from fastapi import APIRouter, Query, HTTPException
from typing import Literal
from .client import StockTwitsClient
from .models import GlobalFeedParam, SymbolFeedParam

router = APIRouter(prefix="/social_feeds", tags=["Social Feed"])

client = StockTwitsClient()


@router.get("/global/{feed}")
async def get_global_feed(
    feed: Literal["trending", "suggested", "popular"],
    limit: int = Query(10, ge=1, le=100),
):
    """
    Get global feeds from StockTwits (trending, suggested, popular).
    """
    try:
        param = GlobalFeedParam(feed=feed, limit=limit)
        return await client.fetch(param)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{symbol}/{feed}")
async def get_symbol_feed(
    symbol: str,
    feed: Literal["trending", "popular"],
    limit: int = Query(10, ge=1, le=100),
):
    """
    Get symbol-specific feeds from StockTwits.
    """
    try:
        param = SymbolFeedParam(feed="symbol", filter=feed, symbol=symbol, limit=limit)
        return await client.fetch(param)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
