from fastapi import APIRouter, Query, Depends
from typing import Any
from api.deps import get_symbol_provider, get_fs, get_settings
from internal.features.symbols.provider import SymbolProvider
from internal.features.symbols import sync_symbols
from api.config import Settings

router = APIRouter(prefix="/api/symbols", tags=["symbols"])


@router.get("/")
async def get_symbols(
    q: str | None = Query(None, description="Search by ticker, name or ISIN"),
    market: str | None = Query(
        "india", description="Filter by market (e.g. india, america)"
    ),
    symbol_type: str | None = Query(
        None, alias="type", description="Filter by instrument type (e.g. stock, etf)"
    ),
    index: str | None = Query(None, description="Filter by index name"),
    limit: int = Query(100, ge=1, le=500),
    provider: SymbolProvider = Depends(get_symbol_provider),
):
    """
    Search for symbols with optional filters.
    """
    return await provider.search(
        query=q, market=market, item_type=symbol_type, index=index, limit=limit
    )


@router.get("/search_metadata")
async def get_metadata(provider: SymbolProvider = Depends(get_symbol_provider)):
    """
    Returns available filter options (markets, indexes, types).
    """
    return provider.get_metadata()


@router.post("/sync")
async def trigger_sync(
    provider: SymbolProvider = Depends(get_symbol_provider),
    fs: Any = Depends(get_fs),
    settings: Settings = Depends(get_settings),
):
    """
    Trigger a manual sync of symbols from TradingView.
    Synchronous (foreground) execution.
    """
    # 1. Fetch from TradingView and persist to storage
    count = await sync_symbols(fs=fs, bucket=settings.oci_bucket)

    # 2. Refresh the provider from storage
    await provider.refresh(trigger_sync=False)

    return {"status": "Sync complete", "count": count}
