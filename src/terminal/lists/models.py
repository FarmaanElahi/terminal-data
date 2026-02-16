from typing import Optional
from uuid import uuid7
from sqlmodel import SQLModel, Field, Column, JSON
from sqlalchemy import ARRAY, String
from pydantic import ConfigDict
from terminal.lists.enums import ListType


def uuid7_str() -> str:
    return str(uuid7())


class List(SQLModel, table=True):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    """
    Unified List model for Simple, Color, and Combo lists.
    """

    id: str = Field(
        default_factory=uuid7_str,
        primary_key=True,
    )
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
