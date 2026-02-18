from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from terminal.dependencies import get_session
from terminal.lists.models import (
    ListCreate,
    ListUpdate,
    SymbolsUpdate,
    SourceListsUpdate,
    ListPublic,
)
from terminal.lists import service as lists_service
from terminal.lists.enums import ListType
from terminal.auth.router import get_current_user
from terminal.auth.models import User

router = APIRouter(prefix="/list", tags=["List"])


@router.get("/", response_model=list[ListPublic])
async def get_all_lists(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """List all lists owned by the current user."""
    lists_service.ensure_default_lists(session, current_user.id)
    return lists_service.get_all(session, current_user.id)


@router.post("/", response_model=ListPublic)
async def create_list(
    data: ListCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Create a new list for the current user."""
    return lists_service.create(
        session,
        user_id=current_user.id,
        data=data,
    )


@router.get("/{id}", response_model=ListPublic)
async def get_list(
    id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get list details and its symbols (aggregated for Combo lists)."""
    lst = lists_service.get(session, id, user_id=current_user.id)
    if not lst:
        raise HTTPException(status_code=404, detail="List not found")

    symbols = lists_service.get_symbols(session, lst, user_id=current_user.id)
    return {
        "id": lst.id,
        "user_id": lst.user_id,
        "name": lst.name,
        "type": lst.type,
        "color": lst.color,
        "symbols": symbols,
        "source_list_ids": lst.source_list_ids,
    }


@router.put("/{id}", response_model=ListPublic)
async def update_list(
    id: str,
    data: ListUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Update list attributes (name, color only)."""
    lst = lists_service.get(session, id, user_id=current_user.id)
    if not lst:
        raise HTTPException(status_code=404, detail="List not found")

    return lists_service.update(session, lst, data)


@router.post("/{id}/append_symbols", response_model=ListPublic)
async def append_symbols(
    id: str,
    data: SymbolsUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Bulk add symbols to a list."""
    lst = lists_service.get(session, id, user_id=current_user.id)
    if not lst:
        raise HTTPException(status_code=404, detail="List not found")

    if lst.type == ListType.combo:
        raise HTTPException(
            status_code=400, detail="Cannot append symbols to a COMBO list"
        )

    return lists_service.append_symbols(session, lst, current_user.id, data)


@router.post("/{id}/bulk_remove_symbols", response_model=ListPublic)
async def bulk_remove_symbols(
    id: str,
    data: SymbolsUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Bulk remove symbols from a list."""
    lst = lists_service.get(session, id, user_id=current_user.id)
    if not lst:
        raise HTTPException(status_code=404, detail="List not found")

    if lst.type == ListType.combo:
        raise HTTPException(
            status_code=400, detail="Cannot remove symbols from a COMBO list"
        )

    return lists_service.bulk_remove_symbols(session, lst, data)


@router.post("/{id}/append_source_lists", response_model=ListPublic)
async def append_source_lists(
    id: str,
    data: SourceListsUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Bulk add source list IDs to a COMBO list."""
    lst = lists_service.get(session, id, user_id=current_user.id)
    if not lst:
        raise HTTPException(status_code=404, detail="List not found")

    if lst.type != ListType.combo:
        raise HTTPException(
            status_code=400, detail="Can only append source lists to a COMBO list"
        )

    return lists_service.append_source_lists(session, lst, data)


@router.post("/{id}/bulk_remove_source_lists", response_model=ListPublic)
async def bulk_remove_source_lists(
    id: str,
    data: SourceListsUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Bulk remove source list IDs from a COMBO list."""
    lst = lists_service.get(session, id, user_id=current_user.id)
    if not lst:
        raise HTTPException(status_code=404, detail="List not found")

    if lst.type != ListType.combo:
        raise HTTPException(
            status_code=400, detail="Can only remove source lists from a COMBO list"
        )

    return lists_service.bulk_remove_source_lists(session, lst, data)
