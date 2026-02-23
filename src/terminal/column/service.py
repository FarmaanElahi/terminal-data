"""CRUD service for column sets."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from terminal.column.models import (
    ColumnSet,
    ColumnSetCreate,
    ColumnSetUpdate,
)


def all(session: Session, user_id: str) -> list[ColumnSet]:
    """List all column sets for a user."""
    return list(
        session.execute(select(ColumnSet).where(ColumnSet.user_id == user_id))
        .scalars()
        .all()
    )


def get(session: Session, user_id: str, column_set_id: str) -> ColumnSet | None:
    """Get a column set by ID."""
    return (
        session.execute(
            select(ColumnSet).where(
                ColumnSet.user_id == user_id, ColumnSet.id == column_set_id
            )
        )
        .scalars()
        .first()
    )


def create(session: Session, user_id: str, column_set_in: ColumnSetCreate) -> ColumnSet:
    """Create a new column set."""
    column_set = ColumnSet(
        user_id=user_id,
        name=column_set_in.name,
        columns=[c.model_dump() for c in column_set_in.columns],
    )
    session.add(column_set)
    session.commit()
    session.refresh(column_set)
    return column_set


def update(
    session: Session,
    user_id: str,
    column_set_id: str,
    column_set_in: ColumnSetUpdate,
) -> ColumnSet | None:
    """Update an existing column set."""
    column_set = get(session, user_id, column_set_id)
    if not column_set:
        return None

    update_data = column_set_in.model_dump(exclude_unset=True)
    if "columns" in update_data and update_data["columns"] is not None:
        update_data["columns"] = [
            c if isinstance(c, dict) else dict(c) for c in update_data["columns"]
        ]

    for field, value in update_data.items():
        setattr(column_set, field, value)

    session.commit()
    session.refresh(column_set)
    return column_set


def delete(session: Session, user_id: str, column_set_id: str) -> bool:
    """Delete a column set."""
    column_set = get(session, user_id, column_set_id)
    if not column_set:
        return False
    session.delete(column_set)
    session.commit()
    return True
