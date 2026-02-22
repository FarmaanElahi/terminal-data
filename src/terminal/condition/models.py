"""Models for the condition module."""

from typing import Literal

from pydantic import BaseModel
from sqlalchemy import String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from terminal.database.core import Base
from terminal.models import PrimaryKeyModel, TerminalBase, TimeStampMixin

# ---------------------------------------------------------------------------
# Timeframe type aliases
# ---------------------------------------------------------------------------

TimeframeLiteral = Literal["D", "W", "M", "Y"]
TimeframeMode = Literal["fixed", "mixed"]


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class Condition(BaseModel):
    """A single condition: a formula expression evaluating to true/false."""

    formula: str
    timeframe: TimeframeLiteral | None = None  # used when parent mode is "mixed"


class ConditionSetCreate(TerminalBase):
    """Schema for creating a condition set."""

    name: str
    conditions: list[Condition] = []
    conditional_logic: Literal["and", "or"] = "and"
    timeframe: TimeframeMode | None = None
    timeframe_value: TimeframeLiteral | None = None  # used when timeframe is "fixed"


class ConditionSetUpdate(TerminalBase):
    """Schema for updating an existing condition set."""

    name: str | None = None
    conditions: list[Condition] | None = None
    conditional_logic: Literal["and", "or"] | None = None
    timeframe: TimeframeMode | None = None
    timeframe_value: TimeframeLiteral | None = None


class ConditionSetPublic(TerminalBase):
    """Schema for returning a condition set."""

    id: str
    name: str
    conditions: list[Condition] = []
    conditional_logic: Literal["and", "or"] = "and"
    timeframe: TimeframeMode | None = None
    timeframe_value: TimeframeLiteral | None = None


# ---------------------------------------------------------------------------
# SQLAlchemy model
# ---------------------------------------------------------------------------


class ConditionSet(Base, PrimaryKeyModel, TimeStampMixin):
    """Reusable condition set created by a user.

    Contains a list of boolean formula conditions joined by AND/OR logic.
    Timeframe can be null (inherit), fixed (shared D/W/M/Y), or mixed
    (each condition defines its own).
    """

    __tablename__ = "condition_sets"

    user_id: Mapped[str] = mapped_column(index=True)
    name: Mapped[str]

    # List of Condition dicts stored as JSONB
    conditions: Mapped[list] = mapped_column(JSONB, default=list)
    conditional_logic: Mapped[str] = mapped_column(String, default="and")

    # Timeframe mode: null | "fixed" | "mixed"
    timeframe: Mapped[str | None] = mapped_column(String, nullable=True, default=None)
    # Actual timeframe value when mode is "fixed" (D/W/M/Y)
    timeframe_value: Mapped[str | None] = mapped_column(
        String, nullable=True, default=None
    )
