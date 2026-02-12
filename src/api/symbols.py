from fastapi import APIRouter, Query, BackgroundTasks
from typing import List, Optional
from features.symbols import (
    search_symbols,
    get_search_metadata,
    clear_cache,
    sync_symbols,
)

router = APIRouter(prefix="/api/symbols", tags=["symbols"])


@router.get("/")
async def get_symbols(
    q: Optional[str] = Query(None, description="Search by ticker, name or ISIN"),
    country: Optional[str] = Query("India", description="Filter by country"),
    index: Optional[str] = Query(None, description="Filter by index name"),
    limit: int = Query(100, ge=1, le=500),
):
    """
    Search for symbols with optional filters.
    """
    return search_symbols(query=q, country=country, index=index, limit=limit)


@router.get("/search_metadata")
async def get_metadata():
    """
    Returns available filter options (countries, indexes).
    """
    return get_search_metadata()


@router.post("/sync")
async def trigger_sync(background_tasks: BackgroundTasks):
    """
    Trigger a manual sync of symbols from TradingView.
    """
    background_tasks.add_task(_perform_sync)
    return {"status": "Sync started in background"}


async def _perform_sync():
    await sync_symbols()
    clear_cache()
