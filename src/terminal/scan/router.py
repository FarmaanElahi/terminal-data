from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from fsspec import AbstractFileSystem
from terminal.auth.router import get_current_user
from terminal.dependencies import get_market_manager, get_session, get_fs, get_settings
from terminal.lists import service as lists_service
from terminal.market_feed.manager import MarketDataManager
from terminal.scan import engine, service
from terminal.scan.formula.router import formulas as formula_router
from terminal.config import Settings
from terminal.scan.models import (
    ScanCreate,
    ScanPublic,
    ScanUpdate,
    ScanStatelessRequest,
)

scans = APIRouter(prefix="/scans", tags=["scans"])

# Mount the formula sub-router under /scans/formula/*
scans.include_router(formula_router)


@scans.get("/", response_model=list[ScanPublic])
def all(
    user: dict = Depends(get_current_user), session: Session = Depends(get_session)
):
    return service.all(session, user["sub"])


@scans.post("/", response_model=ScanPublic)
def create(
    scan_in: ScanCreate,
    user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    return service.create(session, user["sub"], scan_in)


@scans.get("/{scan_id}", response_model=ScanPublic)
def get(
    scan_id: str,
    user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    scan = service.get(session, user["sub"], scan_id)
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
    scan = service.update(session, user["sub"], scan_id, scan_in)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    return scan


@scans.delete("/{scan_id}")
def delete(
    scan_id: str,
    user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    if not service.delete(session, user["sub"], scan_id):
        raise HTTPException(status_code=404, detail="Scan not found")
    return {"ok": True}


@scans.post("/run")
async def run_scan(
    scan_in: ScanStatelessRequest,
    user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
    market_manager: "MarketDataManager" = Depends(get_market_manager),
    fs: AbstractFileSystem = Depends(get_fs),
    settings: Settings = Depends(get_settings),
):
    """Run a stateless scan without persisting."""
    symbols = await _resolve_symbols(scan_in.source, user["sub"], session, fs, settings)
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
