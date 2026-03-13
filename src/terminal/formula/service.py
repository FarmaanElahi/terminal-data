"""CRUD service for user-defined formula functions."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from terminal.formula import fields
from terminal.formula.functions import registered_names
from terminal.formula.params import preprocess
from terminal.formula.parser import parse
from terminal.formula.models import Formula, FormulaCreate


async def create(session: AsyncSession, user_id: str, req: FormulaCreate) -> Formula:
    """Create a user-defined formula.

    Preprocesses the raw multi-line formula to extract body + params,
    validates that the name doesn't collide with built-in fields/functions,
    and stores the result.
    """
    name_upper = req.name.strip().upper()

    # Validate name
    if not name_upper or not name_upper.isidentifier():
        raise ValueError("Formula name must be a valid identifier")

    if fields.is_known(name_upper):
        raise ValueError(f'"{req.name}" collides with a built-in field name')

    if name_upper in registered_names():
        raise ValueError(f'"{req.name}" collides with a built-in function name')

    if name_upper in {"AND", "OR", "NOT", "PARAM"}:
        raise ValueError(f'"{req.name}" is a reserved keyword')

    # Check uniqueness for this user
    existing = (
        (await session.execute(
            select(Formula).where(
                Formula.user_id == user_id, Formula.name == name_upper
            )
        ))
        .scalars()
        .first()
    )
    if existing:
        raise ValueError(f'A formula named "{req.name}" already exists')

    # Preprocess: extract params + body
    body, params = preprocess(req.formula)

    # Validate the formula body parses correctly
    parse(body, params=params)

    formula = Formula(
        user_id=user_id,
        name=name_upper,
        body=body,
        params=params,
    )
    session.add(formula)
    await session.commit()
    await session.refresh(formula)
    return formula


async def all(session: AsyncSession, user_id: str) -> list[Formula]:
    """List all user-defined formulas for a user."""
    return list(
        (await session.execute(select(Formula).where(Formula.user_id == user_id)))
        .scalars()
        .all()
    )


async def get(session: AsyncSession, user_id: str, formula_id: str) -> Formula | None:
    """Get a formula by ID."""
    return (
        (await session.execute(
            select(Formula).where(Formula.user_id == user_id, Formula.id == formula_id)
        ))
        .scalars()
        .first()
    )


async def delete(session: AsyncSession, user_id: str, formula_id: str) -> bool:
    """Delete a user-defined formula."""
    formula = await get(session, user_id, formula_id)
    if not formula:
        return False
    await session.delete(formula)
    await session.commit()
    return True
