"""CRUD service for column sets."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from terminal.column.models import (
    ColumnSet,
    ColumnSetCreate,
    ColumnSetUpdate,
)


async def all(session: AsyncSession, user_id: str) -> list[ColumnSet]:
    """List all column sets for a user."""
    return list(
        (await session.execute(select(ColumnSet).where(ColumnSet.user_id == user_id)))
        .scalars()
        .all()
    )


async def get(session: AsyncSession, user_id: str, column_set_id: str) -> ColumnSet | None:
    """Get a column set by ID."""
    return (
        (await session.execute(
            select(ColumnSet).where(
                ColumnSet.user_id == user_id, ColumnSet.id == column_set_id
            )
        ))
        .scalars()
        .first()
    )


async def create(session: AsyncSession, user_id: str, column_set_in: ColumnSetCreate) -> ColumnSet:
    """Create a new column set."""
    column_set = ColumnSet(
        user_id=user_id,
        name=column_set_in.name,
        columns=[c.model_dump() for c in column_set_in.columns],
    )
    session.add(column_set)
    await session.commit()
    await session.refresh(column_set)
    return column_set


async def update(
    session: AsyncSession,
    user_id: str,
    column_set_id: str,
    column_set_in: ColumnSetUpdate,
) -> ColumnSet | None:
    """Update an existing column set."""
    column_set = await get(session, user_id, column_set_id)
    if not column_set:
        return None

    update_data = column_set_in.model_dump(exclude_unset=True)
    if "columns" in update_data and update_data["columns"] is not None:
        update_data["columns"] = [
            c if isinstance(c, dict) else dict(c) for c in update_data["columns"]
        ]

    for field, value in update_data.items():
        setattr(column_set, field, value)

    await session.commit()
    await session.refresh(column_set)
    return column_set


async def delete(session: AsyncSession, user_id: str, column_set_id: str) -> bool:
    """Delete a column set."""
    column_set = await get(session, user_id, column_set_id)
    if not column_set:
        return False
    await session.delete(column_set)
    await session.commit()
    return True
