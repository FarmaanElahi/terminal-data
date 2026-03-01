from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from terminal.dependencies import get_session
from terminal.auth.router import get_current_user
from terminal.auth.models import User
from terminal.preferences import service
from terminal.preferences.models import PreferencesPublic, PreferencesUpdate

router = APIRouter(prefix="/preferences", tags=["Preferences"])


@router.get("", response_model=PreferencesPublic)
def get_preferences(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    prefs = service.get(session, current_user.id)
    if prefs is None:
        return PreferencesPublic()
    return PreferencesPublic(layout=prefs.layout, settings=prefs.settings)


@router.put("", response_model=PreferencesPublic)
def update_preferences(
    data: PreferencesUpdate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    prefs = service.upsert(session, current_user.id, data)
    return PreferencesPublic(layout=prefs.layout, settings=prefs.settings)
