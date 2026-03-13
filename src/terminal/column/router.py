"""Router for column sets."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from terminal.auth.models import User
from terminal.auth.router import get_current_user
from terminal.column import service
from terminal.column.models import (
    ColumnSetCreate,
    ColumnSetPublic,
    ColumnSetUpdate,
)
from terminal.dependencies import get_session

column_sets = APIRouter(prefix="/columns", tags=["columns"])


@column_sets.get("/", response_model=list[ColumnSetPublic])
async def all(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """List all column sets for the current user."""
    return await service.all(session, user.id)


@column_sets.post("/", response_model=ColumnSetPublic)
async def create(
    column_set_in: ColumnSetCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Create a new column set."""
    return await service.create(session, user.id, column_set_in)


@column_sets.get("/{column_set_id}", response_model=ColumnSetPublic)
async def get(
    column_set_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Get a column set by ID."""
    cs = await service.get(session, user.id, column_set_id)
    if not cs:
        raise HTTPException(status_code=404, detail="Column set not found")
    return cs


@column_sets.put("/{column_set_id}", response_model=ColumnSetPublic)
async def update(
    column_set_id: str,
    column_set_in: ColumnSetUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Update a column set."""
    cs = await service.update(session, user.id, column_set_id, column_set_in)
    if not cs:
        raise HTTPException(status_code=404, detail="Column set not found")
    return cs


@column_sets.delete("/{column_set_id}")
async def delete(
    column_set_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Delete a column set."""
    if not await service.delete(session, user.id, column_set_id):
        raise HTTPException(status_code=404, detail="Column set not found")
    return {"ok": True}
