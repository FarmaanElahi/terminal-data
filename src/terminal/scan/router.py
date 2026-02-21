from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from fsspec import AbstractFileSystem
from terminal.auth.router import get_current_user
from terminal.dependencies import get_market_manager, get_session, get_fs, get_settings
from terminal.lists import service as lists_service
from terminal.market_feed.manager import MarketDataManager
from terminal.scan import engine, service
from terminal.config import Settings
from terminal.scan.models import (
    ScanCreate,
    ScanPublic,
    ScanUpdate,
    ScanStatelessRequest,
)

scans = APIRouter(prefix="/scans", tags=["scans"])


@scans.get("/", response_model=list[ScanPublic])
def all(
    user: dict = Depends(get_current_user), session: Session = Depends(get_session)
):
    """Get all scans for the current user."""
    return service.all(session, user.id)


@scans.post("/", response_model=ScanPublic)
def create(
    scan_in: ScanCreate,
    user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Create a new scan."""
    return service.create(session, user.id, scan_in)


@scans.get("/{scan_id}", response_model=ScanPublic)
def get(
    scan_id: str,
    user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Get a specific scan."""
    scan = service.get(session, user.id, scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    return scan


@scans.put("/{scan_id}", response_model=ScanPublic)
def update(
    scan_id: str,
    scan_in: ScanUpdate,
    user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Update a specific scan."""
    scan = service.update(session, user.id, scan_id, scan_in)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    return scan


@scans.delete("/{scan_id}")
def delete(
    scan_id: str,
    user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Delete a specific scan."""
    success = service.delete(session, user.id, scan_id)
    if not success:
        raise HTTPException(status_code=404, detail="Scan not found")
    return {"ok": True}


@scans.post("/{scan_id}/run")
async def run_scan(
    scan_id: str,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    session: Session = Depends(get_session),
    fs: AbstractFileSystem = Depends(get_fs),
    market_manager: "MarketDataManager" = Depends(get_market_manager),
):

    # 1. Get the Scan
    scan = service.get(session, user.id, scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")

    symbols = await _resolve_symbols(scan.source, user.id, session, fs, settings)
    if not symbols:
        return {"total": 0, "columns": [], "tickers": [], "values": []}

    # 3. Process the engine
    results = engine.run_scan_engine(scan, symbols, market_manager)
    return results


@scans.post("/run_stateless")
async def run_stateless(
    scan_in: ScanStatelessRequest,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    session: Session = Depends(get_session),
    fs: AbstractFileSystem = Depends(get_fs),
    market_manager: "MarketDataManager" = Depends(get_market_manager),
):
    """Run a scan without persisting it."""
    symbols = await _resolve_symbols(scan_in.source, user.id, session, fs, settings)
    if not symbols:
        return {"total": 0, "columns": [], "tickers": [], "values": []}

    # Process the engine
    results = engine.run_scan_engine(scan_in, symbols, market_manager)
    return results


async def _resolve_symbols(
    source: str | None,
    user_id: str,
    session: Session,
    fs: AbstractFileSystem,
    settings: Settings,
) -> list[str]:
    """Helper to resolve symbols from a source list or search all."""
    if not source:
        from terminal.symbols import service as symbols_service

        raw_symbols = await symbols_service.search(fs, settings, limit=100000)
        return [s["ticker"] for s in raw_symbols]
    else:
        lst = lists_service.get(session, source, user_id=user_id)
        if not lst:
            raise HTTPException(status_code=404, detail="Source list not found")

        return lists_service.get_symbols(session, lst, user_id=user_id)
