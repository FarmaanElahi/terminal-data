import asyncio
import logging
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from fsspec import AbstractFileSystem

from terminal.database.core import AsyncSessionLocal
from terminal.dependencies import get_session, get_fs, get_settings
from terminal.auth.router import get_current_user
from terminal.auth.models import User
from terminal.config import Settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/boot", tags=["Boot"])


@router.get("")
async def boot(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    fs: AbstractFileSystem = Depends(get_fs),
    settings: Settings = Depends(get_settings),
):
    """Return all user data needed for UI initialization in a single request."""
    from terminal.lists import service as lists_service
    from terminal.column import service as column_service
    from terminal.condition import service as condition_service
    from terminal.formula import service as formula_service
    from terminal.symbols import service as symbols_service
    from terminal.preferences import service as preferences_service
    from terminal.formula.monaco import editor_config
    from terminal.utils.compression import compress_objects

    # Ensure default lists exist first, then commit so parallel sessions see the rows.
    await lists_service.ensure_default_lists(session, current_user.id)
    await session.commit()

    # Each DB coroutine opens its own session (one connection each) so all
    # queries truly run in parallel. OCI calls share no connection at all.
    user_id = current_user.id

    async def _user_lists():
        async with AsyncSessionLocal() as s:
            return await lists_service.all(s, user_id)

    async def _column_sets():
        async with AsyncSessionLocal() as s:
            return await column_service.all(s, user_id)

    async def _condition_sets():
        async with AsyncSessionLocal() as s:
            return await condition_service.all(s, user_id)

    async def _formulas():
        async with AsyncSessionLocal() as s:
            return await formula_service.all(s, user_id)

    async def _prefs():
        async with AsyncSessionLocal() as s:
            return await preferences_service.get(s, user_id)

    async def _symbols():
        try:
            return await symbols_service.search(
                fs=fs, settings=settings, market="india", limit=5000
            )
        except Exception as e:
            logger.warning("Could not load symbols for boot: %s", e)
            return []

    (
        user_lists,
        system_lists,
        column_sets,
        condition_sets,
        formulas,
        prefs,
        symbols,
    ) = await asyncio.gather(
        _user_lists(),
        lists_service.get_all_system_lists(fs, settings),
        _column_sets(),
        _condition_sets(),
        _formulas(),
        _prefs(),
        _symbols(),
    )

    symbols_filtered = []
    for s in symbols:
        sym = s if isinstance(s, dict) else (s.model_dump() if hasattr(s, "model_dump") else dict(s))
        symbols_filtered.append({
            "ticker": sym.get("ticker"),
            "name": sym.get("name"),
            "logo": sym.get("logo"),
            "exchange": sym.get("exchange"),
            "market": sym.get("market"),
            "type": sym.get("type"),
            "typespecs": sym.get("typespecs", []),
        })

    return {
        "user": {
            "id": current_user.id,
            "username": current_user.username,
            "is_active": current_user.is_active,
        },
        "lists": user_lists + system_lists,
        "column_sets": column_sets,
        "condition_sets": condition_sets,
        "formulas": formulas,
        "symbols": compress_objects(symbols_filtered),
        "editor_config": editor_config(),
        "preferences": {
            "layout": prefs.layout if prefs else None,
            "settings": prefs.settings if prefs else None,
        },
    }
