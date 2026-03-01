from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from terminal.dependencies import get_session, get_fs, get_settings
from terminal.auth.router import get_current_user
from terminal.auth.models import User

router = APIRouter(prefix="/boot", tags=["Boot"])


@router.get("")
async def boot(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
    fs=Depends(get_fs),
    settings=Depends(get_settings),
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
    symbols = await symbols_service.search(
        fs=None,  # Not needed for cached search
        settings=None,  # Not needed for cached search
        market="india",
        limit=5000,
    )

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
        "symbols": symbols,
        "editor_config": editor_config(),
    }
