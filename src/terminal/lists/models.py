from typing import Optional
from sqlmodel import Field, Column, JSON
from sqlalchemy import ARRAY, String
from terminal.lists.enums import ListType
from terminal.models import PrimaryKeyModel, TimeStampMixin, TerminalBase


class List(PrimaryKeyModel, TimeStampMixin, table=True):
    """
    Unified List model for Simple, Color, and Combo lists.
    """

    name: str
    type: ListType
    color: Optional[str] = None  # e.g., "red", "green", "purple"

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
    color: Optional[str] = None
    source_list_ids: Optional[list[str]] = None


class SymbolUpdate(TerminalBase):
    symbols: list[str]
