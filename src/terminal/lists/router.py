from fastapi import APIRouter, Depends, HTTPException
from fsspec import AbstractFileSystem
from sqlalchemy.ext.asyncio import AsyncSession

from terminal.auth.models import User
from terminal.auth.router import get_current_user
from terminal.config import Settings
from terminal.dependencies import (
    get_fs,
    get_market_manager,
    get_session,
    get_settings,
)
from terminal.lists import service as lists_service
from terminal.lists.enums import ListType
from terminal.lists.models import (
    ListCreate,
    ListPublic,
    ListUpdate,
    SourceListsUpdate,
    SymbolsUpdate,
)
from terminal.market_feed.manager import MarketDataManager

router = APIRouter(prefix="/lists", tags=["List"])


@router.get("", response_model=list[ListPublic])
async def all(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
    fs: AbstractFileSystem = Depends(get_fs),
    settings: Settings = Depends(get_settings),
):
    """List all lists owned by the current user and system lists."""
    await lists_service.ensure_default_lists(session, current_user.id)
    user_lists = await lists_service.all(session, current_user.id)
    system_lists = await lists_service.get_all_system_lists(fs, settings)
    return user_lists + system_lists


@router.post("", response_model=ListPublic)
async def create_list(
    data: ListCreate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Create a new list for the current user."""
    return await lists_service.create(
        session,
        user_id=current_user.id,
        data=data,
    )


@router.get("/{id}", response_model=ListPublic)
async def get(
    id: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
    fs: AbstractFileSystem = Depends(get_fs),
    settings: Settings = Depends(get_settings),
):
    """Get list details and its symbols (aggregated for Combo lists)."""
    if id.startswith(lists_service.SYSTEM_LIST_PREFIX):
        lst = lists_service.get_system_list_by_id(id)
    else:
        lst = await lists_service.get(session, id, user_id=current_user.id)

    if not lst:
        raise HTTPException(status_code=404, detail="List not found")

    symbols = await lists_service.get_symbols_async(
        session, lst, user_id=current_user.id, fs=fs, settings=settings
    )
    return {
        "id": lst.id,
        "user_id": lst.user_id,
        "name": lst.name,
        "type": lst.type,
        "color": lst.color,
        "symbols": symbols,
        "source_list_ids": lst.source_list_ids
        if hasattr(lst, "source_list_ids")
        else [],
    }


@router.put("/{id}", response_model=ListPublic)
async def update_list(
    id: str,
    data: ListUpdate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Update list attributes (name, color only)."""
    lst = await lists_service.get(session, id, user_id=current_user.id)
    if not lst:
        raise HTTPException(status_code=404, detail="List not found")

    return await lists_service.update(session, lst, data)


@router.delete("/{id}", status_code=204)
async def delete_list(
    id: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Delete a list. Color and system lists cannot be deleted."""
    if id.startswith(lists_service.SYSTEM_LIST_PREFIX):
        raise HTTPException(status_code=400, detail="System lists cannot be deleted")

    lst = await lists_service.get(session, id, user_id=current_user.id)
    if not lst:
        raise HTTPException(status_code=404, detail="List not found")

    if lst.type == ListType.color:
        raise HTTPException(status_code=400, detail="Color lists cannot be deleted")

    await lists_service.delete(session, lst)
    return None


@router.put("/{id}/symbols", response_model=ListPublic)
async def set_symbols(
    id: str,
    data: SymbolsUpdate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Replace all symbols in a simple list (preserves order, allows ### section entries)."""
    lst = await lists_service.get(session, id, user_id=current_user.id)
    if not lst:
        raise HTTPException(status_code=404, detail="List not found")

    if lst.type not in (ListType.simple, ListType.color):
        raise HTTPException(
            status_code=400, detail="Can only set symbols on a simple or color list"
        )

    return await lists_service.set_symbols(session, lst, data)


@router.post("/{id}/append_symbols", response_model=ListPublic)
async def append_symbols(
    id: str,
    data: SymbolsUpdate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Bulk add symbols to a list."""
    lst = await lists_service.get(session, id, user_id=current_user.id)
    if not lst:
        raise HTTPException(status_code=404, detail="List not found")

    if lst.type == ListType.combo:
        raise HTTPException(
            status_code=400, detail="Cannot append symbols to a COMBO list"
        )

    return await lists_service.append_symbols(session, lst, current_user.id, data)


@router.post("/{id}/bulk_remove_symbols", response_model=ListPublic)
async def bulk_remove_symbols(
    id: str,
    data: SymbolsUpdate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Bulk remove symbols from a list."""
    lst = await lists_service.get(session, id, user_id=current_user.id)
    if not lst:
        raise HTTPException(status_code=404, detail="List not found")

    if lst.type == ListType.combo:
        raise HTTPException(
            status_code=400, detail="Cannot remove symbols from a COMBO list"
        )

    return await lists_service.bulk_remove_symbols(session, lst, data)


@router.post("/{id}/append_source_lists", response_model=ListPublic)
async def append_source_lists(
    id: str,
    data: SourceListsUpdate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Bulk add source list IDs to a COMBO list."""
    lst = await lists_service.get(session, id, user_id=current_user.id)
    if not lst:
        raise HTTPException(status_code=404, detail="List not found")

    if lst.type != ListType.combo:
        raise HTTPException(
            status_code=400, detail="Can only append source lists to a COMBO list"
        )

    return await lists_service.append_source_lists(session, lst, data)


@router.post("/{id}/bulk_remove_source_lists", response_model=ListPublic)
async def bulk_remove_source_lists(
    id: str,
    data: SourceListsUpdate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Bulk remove source list IDs from a COMBO list."""
    lst = await lists_service.get(session, id, user_id=current_user.id)
    if not lst:
        raise HTTPException(status_code=404, detail="List not found")

    if lst.type != ListType.combo:
        raise HTTPException(
            status_code=400, detail="Can only remove source lists from a COMBO list"
        )

    return await lists_service.bulk_remove_source_lists(session, lst, data)


@router.post("/{id}/scan")
async def run_list_scan(
    id: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
    market_manager: "MarketDataManager" = Depends(get_market_manager),
    fs: AbstractFileSystem = Depends(get_fs),
    settings: Settings = Depends(get_settings),
):
    """Run the scan engine using this list's symbols and column definitions."""
    if id.startswith(lists_service.SYSTEM_LIST_PREFIX):
        lst = lists_service.get_system_list_by_id(id)
    else:
        lst = await lists_service.get(session, id, user_id=current_user.id)

    if not lst:
        raise HTTPException(status_code=404, detail="List not found")

    symbols = await lists_service.get_symbols_async(
        session, lst, user_id=current_user.id, fs=fs, settings=settings
    )
    if not symbols:
        return {"total": 0, "columns": [], "tickers": [], "values": []}

    from terminal.scan import engine

    results = engine.run_scan_engine(lst, symbols, market_manager)
    return results
