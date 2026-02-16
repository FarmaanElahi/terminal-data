from fastapi import APIRouter, Depends
from sqlmodel import Session
from typing import Optional
from pydantic import BaseModel
from terminal.database import get_session
from terminal.lists.service import ListService
from terminal.lists.enums import ListType

router = APIRouter(prefix="/list", tags=["List"])


class ListCreate(BaseModel):
    name: str
    type: ListType
    color: Optional[str] = None
    source_list_ids: Optional[list[str]] = None


class SymbolUpdate(BaseModel):
    symbols: list[str]


@router.get("/")
async def get_all_lists(session: Session = Depends(get_session)):
    """List all available lists."""
    return ListService.get_all_lists(session)


@router.post("/")
async def create_list(data: ListCreate, session: Session = Depends(get_session)):
    """Create a new list (Simple, Color, or Combo)."""
    return ListService.create_list(
        session,
        name=data.name,
        list_type=data.type,
        color=data.color,
        source_list_ids=data.source_list_ids,
    )


@router.get("/{id}")
async def get_list(id: str, session: Session = Depends(get_session)):
    """Get list details and its symbols (aggregated for Combo lists)."""
    lst = ListService.get_list(session, id)
    symbols = ListService.get_symbols(session, id)
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
    return ListService.append_symbols(session, id, data.symbols)


@router.post("/{id}/bulk_remove")
async def bulk_remove_symbols(
    id: str, data: SymbolUpdate, session: Session = Depends(get_session)
):
    """Bulk remove symbols from a list."""
    return ListService.bulk_remove_symbols(session, id, data.symbols)
