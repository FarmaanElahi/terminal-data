from typing import Literal

from pydantic import BaseModel
from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from terminal.database.core import Base
from terminal.models import PrimaryKeyModel, TerminalBase, TimeStampMixin


# Pydantic models for validation / requests


class ColumnDef(BaseModel):
    id: str
    name: str
    type: Literal["value", "condition", "tag"]
    timeframe: Literal["D", "W", "M", "Y"] | None = "D"
    static_property: str | None = None
    expression: str | None = None
    bar_ago: int | None = None


class ConditionParam(BaseModel):
    """Schema representing a condition in a scan or standard payload."""

    formula: str
    true_when: Literal["now", "x_bar_ago", "within_last"] = "now"
    true_when_param: int | None = None
    evaluation_type: Literal["boolean", "rank"] = "boolean"
    type: Literal["computed", "static"] = "computed"
    rank_min: int | None = None
    rank_max: int | None = None


class ScanCreate(TerminalBase):
    """Schema for creating a new scan."""

    name: str
    source: str | None = None
    conditions: list[ConditionParam] = []
    conditional_logic: Literal["and", "or"] = "and"
    columns: list[ColumnDef] = []


class ScanStatelessRequest(TerminalBase):
    """Schema for running a stateless scan."""

    source: str | None = None
    conditions: list[ConditionParam] = []
    conditional_logic: Literal["and", "or"] = "and"
    columns: list[ColumnDef] = []


class ScanUpdate(TerminalBase):
    """Schema for updating an existing scan."""

    name: str | None = None
    source: str | None = None
    conditions: list[ConditionParam] | None = None
    conditional_logic: Literal["and", "or"] | None = None
    columns: list[ColumnDef] | None = None


class ScanPublic(TerminalBase):
    """Schema for returning a scan."""

    id: str
    name: str
    source: str | None = None
    conditions: list[ConditionParam] = []
    conditional_logic: Literal["and", "or"] = "and"
    columns: list[ColumnDef] = []


class Scan(Base, PrimaryKeyModel, TimeStampMixin):
    """Scan definition stored by the user."""

    __tablename__ = "scans"

    user_id: Mapped[str] = mapped_column(index=True)
    name: Mapped[str]
    source: Mapped[str | None] = mapped_column(ForeignKey("lists.id"), nullable=True)

    # Store conditions as JSONB
    conditions: Mapped[list[ConditionParam]] = mapped_column(JSONB, default=list)
    conditional_logic: Mapped[str] = mapped_column(String, default="and")

    # Store column definitions as JSONB
    columns: Mapped[list[ColumnDef]] = mapped_column(JSONB, default=list)
