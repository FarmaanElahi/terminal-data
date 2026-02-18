from fastapi import APIRouter, Query, Depends
from typing import Any
from sqlalchemy.orm import Session
from terminal.dependencies import get_fs, get_settings, get_session
from terminal.symbols import service as symbol_service
from terminal.symbols.models import SymbolSearchResponse
from terminal.symbols.tasks import sync_symbols
from terminal.config import Settings

router = APIRouter(prefix="/symbols", tags=["Symbol"])


@router.get("/", response_model=list[SymbolSearchResponse])
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
    session: Session = Depends(get_session),
):
    """
    Search for symbols with optional filters.
    """
    return await symbol_service.search(
        session=session,
        query=q,
        market=market,
        item_type=symbol_type,
        index=index,
        limit=limit,
    )


@router.get("/search_metadata")
async def get_metadata(
    session: Session = Depends(get_session),
):
    """
    Returns available filter options (markets, indexes, types).
    """
    return symbol_service.get_metadata(session=session)


@router.post("/sync")
async def trigger_sync(
    fs: Any = Depends(get_fs),
    settings: Settings = Depends(get_settings),
    session: Session = Depends(get_session),
):
    """
    Trigger a manual sync of symbols from TradingView.
    Synchronous (foreground) execution.
    """
    # 1. Fetch from TradingView
    symbols = await sync_symbols(fs=fs, bucket=settings.oci_bucket)

    # 2. Refresh the database-backed storage
    count = await symbol_service.refresh(session=session, symbols=symbols)

    return {"status": "Sync complete", "count": count}
