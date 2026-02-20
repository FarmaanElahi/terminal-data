from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from terminal.auth.router import get_current_user
from terminal.dependencies import get_market_manager, get_session
from terminal.lists import service as lists_service
from terminal.market_feed.manager import MarketDataManager
from terminal.scan import engine, service
from terminal.scan.models import (
    ScanCreate,
    ScanPublic,
    ScanUpdate,
)

scans = APIRouter(prefix="/scans", tags=["scans"])


@scans.get("/", response_model=list[ScanPublic])
def get_scans(
    user: dict = Depends(get_current_user), session: Session = Depends(get_session)
):
    """Get all scans for the current user."""
    return service.get_scans(session, user.id)


@scans.post("/", response_model=ScanPublic)
def create_scan(
    scan_in: ScanCreate,
    user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Create a new scan."""
    return service.create_scan(session, user.id, scan_in)


@scans.get("/{scan_id}", response_model=ScanPublic)
def get_scan(
    scan_id: str,
    user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Get a specific scan."""
    scan = service.get_scan(session, user.id, scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    return scan


@scans.put("/{scan_id}", response_model=ScanPublic)
def update_scan(
    scan_id: str,
    scan_in: ScanUpdate,
    user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Update a specific scan."""
    scan = service.update_scan(session, user.id, scan_id, scan_in)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    return scan


@scans.delete("/{scan_id}")
def delete_scan(
    scan_id: str,
    user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Delete a specific scan."""
    success = service.delete_scan(session, user.id, scan_id)
    if not success:
        raise HTTPException(status_code=404, detail="Scan not found")
    return {"ok": True}


@scans.post("/{scan_id}/run")
def run_scan(
    scan_id: str,
    user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
    market_manager: "MarketDataManager" = Depends(get_market_manager),
):

    # 1. Get the Scan
    scan = service.get_scan(session, user.id, scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")

    # 2. Get the target list and symbols
    lst = lists_service.get(session, scan.sources, user_id=user.id)
    if not lst:
        raise HTTPException(status_code=404, detail="Source list not found")

    symbols = lists_service.get_symbols(session, lst, user_id=user.id)
    if not symbols:
        return []

    # 3. Process the engine
    results = engine.run_scan_engine(scan, symbols, market_manager)
    return results
