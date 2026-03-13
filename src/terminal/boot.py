from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from fsspec import AbstractFileSystem

from terminal.dependencies import get_session, get_fs, get_settings
from terminal.auth.router import get_current_user
from terminal.auth.models import User
from terminal.config import Settings

router = APIRouter(prefix="/boot", tags=["Boot"])


@router.get("")
async def boot(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
    fs: AbstractFileSystem = Depends(get_fs),
    settings: Settings = Depends(get_settings),
):
    """Return all user data needed for UI initialization in a single request."""
    from terminal.lists import service as lists_service
    from terminal.column import service as column_service
    from terminal.condition import service as condition_service
    from terminal.formula import service as formula_service
    from terminal.symbols import service as symbols_service
    from terminal.formula.monaco import editor_config

    lists_service.ensure_default_lists(session, current_user.id)

    # Get symbols for local search (default limit)
    try:
        symbols = await symbols_service.search(
            fs=fs,
            settings=settings,
            market="india",
            limit=5000,
        )
    except Exception as e:
        # If symbols can't be loaded (e.g., OCI not configured), return empty list
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Could not load symbols for boot: {e}")
        symbols = []

    from terminal.preferences import service as preferences_service
    from terminal.utils.compression import compress_objects

    prefs = preferences_service.get(session, current_user.id)

    # Filter symbols to only include needed fields
    # ticker is the ID, plus: name, logo, exchange, market, type, typespecs
    symbols_filtered = []
    for s in symbols:
        if isinstance(s, dict):
            sym = s
        else:
            sym = s.model_dump() if hasattr(s, "model_dump") else dict(s)

        # Only include specified fields
        filtered = {
            "ticker": sym.get("ticker"),
            "name": sym.get("name"),
            "logo": sym.get("logo"),
            "exchange": sym.get("exchange"),
            "market": sym.get("market"),
            "type": sym.get("type"),
            "typespecs": sym.get("typespecs", []),
        }
        symbols_filtered.append(filtered)

    return {
        "user": {
            "id": current_user.id,
            "username": current_user.username,
            "is_active": current_user.is_active,
        },
        "lists": lists_service.all(session, current_user.id)
        + await lists_service.get_all_system_lists(fs, settings),
        "column_sets": column_service.all(session, current_user.id),
        "condition_sets": condition_service.all(session, current_user.id),
        "formulas": formula_service.all(session, current_user.id),
        "symbols": compress_objects(symbols_filtered),
        "editor_config": editor_config(),
        "preferences": {
            "layout": prefs.layout if prefs else None,
            "settings": prefs.settings if prefs else None,
        },
    }
