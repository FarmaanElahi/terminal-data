"""Router for condition sets."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

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
async def all(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """List all condition sets for the current user."""
    return await service.all(session, user.id)


@conditions.post("/", response_model=ConditionSetPublic)
async def create(
    condition_set_in: ConditionSetCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Create a new condition set."""
    return await service.create(session, user.id, condition_set_in)


@conditions.get("/{condition_set_id}", response_model=ConditionSetPublic)
async def get(
    condition_set_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Get a condition set by ID."""
    cs = await service.get(session, user.id, condition_set_id)
    if not cs:
        raise HTTPException(status_code=404, detail="Condition set not found")
    return cs


@conditions.put("/{condition_set_id}", response_model=ConditionSetPublic)
async def update(
    condition_set_id: str,
    condition_set_in: ConditionSetUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Update a condition set."""
    cs = await service.update(session, user.id, condition_set_id, condition_set_in)
    if not cs:
        raise HTTPException(status_code=404, detail="Condition set not found")
    return cs


@conditions.delete("/{condition_set_id}")
async def delete(
    condition_set_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Delete a condition set."""
    if not await service.delete(session, user.id, condition_set_id):
        raise HTTPException(status_code=404, detail="Condition set not found")
    return {"ok": True}
