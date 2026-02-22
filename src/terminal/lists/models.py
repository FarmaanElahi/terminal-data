from typing import Literal

from pydantic import BaseModel
from sqlalchemy import ARRAY, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from terminal.condition.models import TimeframeLiteral
from terminal.database.core import Base
from terminal.lists.enums import ListType
from terminal.models import PrimaryKeyModel, TerminalBase, TimeStampMixin


# ---------------------------------------------------------------------------
# Column / Condition Pydantic schemas
# ---------------------------------------------------------------------------


class ColumnDef(BaseModel):
    """Definition of a column attached to a list."""

    id: str
    name: str
    type: Literal["value", "condition", "tag"]
    timeframe: TimeframeLiteral | None = "D"
    formula: str | None = None
    bar_ago: int | None = None
    visible: bool = True
    filter_active: bool = False
    condition_id: str | None = None  # for condition columns


class ConditionParam(BaseModel):
    """Schema representing a condition in a scan or standard payload."""

    formula: str
    true_when: Literal["now", "x_bar_ago", "within_last"] = "now"
    true_when_param: int | None = None
    evaluation_type: Literal["boolean", "rank"] = "boolean"
    type: Literal["computed", "static"] = "computed"
    rank_min: int | None = None
    rank_max: int | None = None


# ---------------------------------------------------------------------------
# SQLAlchemy model
# ---------------------------------------------------------------------------


class List(Base, PrimaryKeyModel, TimeStampMixin):
    """
    Unified List model for Simple, Color, and Combo lists.
    """

    __tablename__ = "lists"

    user_id: Mapped[str] = mapped_column(
        index=True
    )  # user_id should be foreign key in real app
    # user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str]
    type: Mapped[ListType]
    color: Mapped[str | None] = mapped_column(default=None)

    # Store list of symbol strings (e.g., ["NSE:RELIANCE", "NASDAQ:AAPL"])
    symbols: Mapped[list[str]] = mapped_column(
        ARRAY(String),
        default=list,
    )

    # Store list of list IDs for COMBO lists
    source_list_ids: Mapped[list[str]] = mapped_column(
        ARRAY(String),
        default=list,
    )

    # Store column definitions as JSONB
    columns: Mapped[list[ColumnDef]] = mapped_column(JSONB, default=list)


# ---------------------------------------------------------------------------
# Pydantic request / response schemas
# ---------------------------------------------------------------------------


class ListCreate(TerminalBase):
    name: str
    type: ListType
    color: str | None = None
    source_list_ids: list[str] | None = None
    columns: list[ColumnDef] = []


class ListPublic(TerminalBase):
    id: str
    user_id: str
    name: str
    type: ListType
    color: str | None = None
    symbols: list[str] = []
    source_list_ids: list[str] = []
    columns: list[ColumnDef] = []


class ListUpdate(TerminalBase):
    name: str | None = None
    color: str | None = None
    columns: list[ColumnDef] | None = None


class SymbolsUpdate(TerminalBase):
    symbols: list[str]


class SourceListsUpdate(TerminalBase):
    source_list_ids: list[str]
