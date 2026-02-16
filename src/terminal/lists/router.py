from fastapi import APIRouter, Depends
from sqlmodel import Session

from terminal.database import get_session
from terminal.lists.models import List, ListCreate, SymbolUpdate
from terminal.lists import service as lists_service
from terminal.lists.enums import ListType

router = APIRouter(prefix="/list", tags=["List"])


@router.get("/")
async def get_all_lists(session: Session = Depends(get_session)):
    """List all available lists."""
    from sqlmodel import select

    return session.exec(select(List)).all()


@router.post("/")
async def create_list(data: ListCreate, session: Session = Depends(get_session)):
    """Create a new list (Simple, Color, or Combo)."""
    return lists_service.create(
        session,
        name=data.name,
        list_type=data.type,
        color=data.color,
        source_list_ids=data.source_list_ids,
    )


@router.get("/{id}")
async def get_list(id: str, session: Session = Depends(get_session)):
    """Get list details and its symbols (aggregated for Combo lists)."""
    from fastapi import HTTPException

    lst = lists_service.get(session, id)
    if not lst:
        raise HTTPException(status_code=404, detail="List not found")

    symbols = lists_service.get_symbols(session, id)
    return {
        "id": lst.id,
        "name": lst.name,
        "type": lst.type,
        "color": lst.color,
        "symbols": symbols,
        "source_list_ids": lst.source_list_ids,
    }


@router.post("/{id}/append")
async def append_symbols(
    id: str, data: SymbolUpdate, session: Session = Depends(get_session)
):
    """Bulk add symbols to a list."""
    from fastapi import HTTPException

    lst = lists_service.get(session, id)
    if not lst:
        raise HTTPException(status_code=404, detail="List not found")

    if lst.type == ListType.combo:
        raise HTTPException(
            status_code=400, detail="Cannot append symbols to a COMBO list"
        )

    return lists_service.append_symbols(session, id, data.symbols)


@router.post("/{id}/bulk_remove")
async def bulk_remove_symbols(
    id: str, data: SymbolUpdate, session: Session = Depends(get_session)
):
    """Bulk remove symbols from a list."""
    from fastapi import HTTPException

    lst = lists_service.get(session, id)
    if not lst:
        raise HTTPException(status_code=404, detail="List not found")

    if lst.type == ListType.combo:
        raise HTTPException(
            status_code=400, detail="Cannot remove symbols from a COMBO list"
        )

    return lists_service.bulk_remove_symbols(session, id, data.symbols)
