"""CRUD service for condition sets."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from terminal.condition.models import (
    ConditionSet,
    ConditionSetCreate,
    ConditionSetUpdate,
)


def all(session: Session, user_id: str) -> list[ConditionSet]:
    """List all condition sets for a user."""
    return list(
        session.execute(select(ConditionSet).where(ConditionSet.user_id == user_id))
        .scalars()
        .all()
    )


def get(session: Session, user_id: str, condition_set_id: str) -> ConditionSet | None:
    """Get a condition set by ID."""
    return (
        session.execute(
            select(ConditionSet).where(
                ConditionSet.user_id == user_id, ConditionSet.id == condition_set_id
            )
        )
        .scalars()
        .first()
    )


def create(
    session: Session, user_id: str, condition_set_in: ConditionSetCreate
) -> ConditionSet:
    """Create a new condition set."""
    condition_set = ConditionSet(
        user_id=user_id,
        name=condition_set_in.name,
        conditions=[c.model_dump() for c in condition_set_in.conditions],
        conditional_logic=condition_set_in.conditional_logic,
        timeframe=condition_set_in.timeframe,
        timeframe_value=condition_set_in.timeframe_value,
    )
    session.add(condition_set)
    session.commit()
    session.refresh(condition_set)
    return condition_set


def update(
    session: Session,
    user_id: str,
    condition_set_id: str,
    condition_set_in: ConditionSetUpdate,
) -> ConditionSet | None:
    """Update an existing condition set."""
    condition_set = get(session, user_id, condition_set_id)
    if not condition_set:
        return None

    update_data = condition_set_in.model_dump(exclude_unset=True)
    if "conditions" in update_data and update_data["conditions"] is not None:
        update_data["conditions"] = [
            c if isinstance(c, dict) else dict(c) for c in update_data["conditions"]
        ]

    for field, value in update_data.items():
        setattr(condition_set, field, value)

    session.commit()
    session.refresh(condition_set)
    return condition_set


def delete(session: Session, user_id: str, condition_set_id: str) -> bool:
    """Delete a condition set."""
    condition_set = get(session, user_id, condition_set_id)
    if not condition_set:
        return False
    session.delete(condition_set)
    session.commit()
    return True
