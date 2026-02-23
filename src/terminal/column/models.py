"""Models for the column module."""

from typing import Literal

from pydantic import BaseModel
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from terminal.condition.models import TimeframeLiteral
from terminal.database.core import Base
from terminal.models import PrimaryKeyModel, TerminalBase, TimeStampMixin


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class ColumnDef(BaseModel):
    """Definition of a single column within a ColumnSet."""

    id: str
    name: str
    type: Literal["value", "condition", "tag"]
    timeframe: TimeframeLiteral | None = "D"
    formula: str | None = None
    bar_ago: int | None = None
    visible: bool = True
    condition_id: str | None = None  # reference to a ConditionSet
    condition_logic: Literal["and", "or"] = "and"
    filter: Literal["active", "inactive", "off"] = "off"


class ColumnSetCreate(TerminalBase):
    """Schema for creating a column set."""

    name: str
    columns: list[ColumnDef] = []


class ColumnSetUpdate(TerminalBase):
    """Schema for updating an existing column set."""

    name: str | None = None
    columns: list[ColumnDef] | None = None


class ColumnSetPublic(TerminalBase):
    """Schema for returning a column set."""

    id: str
    name: str
    columns: list[ColumnDef] = []


# ---------------------------------------------------------------------------
# SQLAlchemy model
# ---------------------------------------------------------------------------


class ColumnSet(Base, PrimaryKeyModel, TimeStampMixin):
    """Reusable column set created by a user.

    Contains a list of column definitions stored as JSONB.
    """

    __tablename__ = "column_sets"

    user_id: Mapped[str] = mapped_column(index=True)
    name: Mapped[str]

    # List of ColumnDef dicts stored as JSONB
    columns: Mapped[list] = mapped_column(JSONB, default=list)
