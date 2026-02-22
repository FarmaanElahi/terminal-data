"""Router for condition sets."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from terminal.auth.models import User
from terminal.auth.router import get_current_user
from terminal.condition import service
from terminal.condition.models import (
    ConditionSetCreate,
    ConditionSetPublic,
    ConditionSetUpdate,
)
from terminal.dependencies import get_session

conditions = APIRouter(prefix="/conditions", tags=["conditions"])


@conditions.get("/", response_model=list[ConditionSetPublic])
def all(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """List all condition sets for the current user."""
    return service.all(session, user.id)


@conditions.post("/", response_model=ConditionSetPublic)
def create(
    condition_set_in: ConditionSetCreate,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Create a new condition set."""
    return service.create(session, user.id, condition_set_in)


@conditions.get("/{condition_set_id}", response_model=ConditionSetPublic)
def get(
    condition_set_id: str,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Get a condition set by ID."""
    cs = service.get(session, user.id, condition_set_id)
    if not cs:
        raise HTTPException(status_code=404, detail="Condition set not found")
    return cs


@conditions.put("/{condition_set_id}", response_model=ConditionSetPublic)
def update(
    condition_set_id: str,
    condition_set_in: ConditionSetUpdate,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Update a condition set."""
    cs = service.update(session, user.id, condition_set_id, condition_set_in)
    if not cs:
        raise HTTPException(status_code=404, detail="Condition set not found")
    return cs


@conditions.delete("/{condition_set_id}")
def delete(
    condition_set_id: str,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Delete a condition set."""
    if not service.delete(session, user.id, condition_set_id):
        raise HTTPException(status_code=404, detail="Condition set not found")
    return {"ok": True}
