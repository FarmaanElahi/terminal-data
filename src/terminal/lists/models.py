from sqlmodel import Field, Column, JSON
from sqlalchemy import ARRAY, String
from terminal.lists.enums import ListType
from terminal.models import PrimaryKeyModel, TimeStampMixin, TerminalBase


class List(PrimaryKeyModel, TimeStampMixin, table=True):
    """
    Unified List model for Simple, Color, and Combo lists.
    """

    __tablename__ = "lists"

    user_id: str = Field(foreign_key="users.id", index=True)
    name: str
    type: ListType
    color: str | None = None  # e.g., "red", "green", "purple"

    # Store list of symbol strings (e.g., ["NSE:RELIANCE", "NASDAQ:AAPL"])
    symbols: list[str] = Field(
        default_factory=list,
        sa_column=Column(ARRAY(String).with_variant(JSON, "sqlite")),
    )

    # Store list of list IDs for COMBO lists
    source_list_ids: list[str] = Field(
        default_factory=list,
        sa_column=Column(ARRAY(String).with_variant(JSON, "sqlite")),
    )


class ListCreate(TerminalBase):
    name: str
    type: ListType
    color: str | None = None
    source_list_ids: list[str] | None = None


class ListUpdate(TerminalBase):
    name: str | None = None
    color: str | None = None


class SymbolsUpdate(TerminalBase):
    symbols: list[str]


class SourceListsUpdate(TerminalBase):
    source_list_ids: list[str]
