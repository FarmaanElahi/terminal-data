from fastapi import APIRouter, Depends, Query
from fsspec import AbstractFileSystem

from terminal.config import Settings
from terminal.dependencies import get_fs, get_settings
from terminal.symbols import service as symbol_service
from terminal.symbols.models import SearchResultResponse

router = APIRouter(prefix="/symbols", tags=["Symbol"])


@router.get("/q", response_model=SearchResultResponse)
async def get_symbols(
    q: str | None = Query(None, description="Search by ticker, name or ISIN"),
    market: str | None = Query(
        "india", description="Filter by market (e.g. india, america)"
    ),
    symbol_type: str | None = Query(
        None, alias="type", description="Filter by instrument type (e.g. stock, etf)"
    ),
    index: str | None = Query(None, description="Filter by index name"),
    limit: int = Query(100, ge=1, le=50000),
    fs: AbstractFileSystem = Depends(get_fs),
    settings: Settings = Depends(get_settings),
):
    """
    Search for symbols with optional filters.
    """
    items = await symbol_service.search(
        fs=fs,
        settings=settings,
        text=q,
        market=market,
        item_type=symbol_type,
        index=index,
        limit=limit,
    )
    return {"items": items}


@router.get("/search_metadata")
async def get_metadata(
    fs: AbstractFileSystem = Depends(get_fs),
    settings: Settings = Depends(get_settings),
):
    """
    Returns available filter options (markets, indexes, types).
    """
    return await symbol_service.get_filter_metadata(fs=fs, settings=settings)


@router.post("/sync")
async def trigger_sync(
    fs: AbstractFileSystem = Depends(get_fs),
    settings: Settings = Depends(get_settings),
):
    """
    Trigger a manual sync of symbols from TradingView.
    Synchronous (foreground) execution.
    """
    count = await symbol_service.refresh(fs=fs, settings=settings)
    await symbol_service.init(fs, settings)

    return {"status": "Sync complete", "count": count}
