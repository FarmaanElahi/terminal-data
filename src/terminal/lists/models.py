from sqlalchemy import ARRAY, String
from sqlalchemy.orm import Mapped, mapped_column

from terminal.database.core import Base
from terminal.lists.enums import ListType
from terminal.models import PrimaryKeyModel, TerminalBase, TimeStampMixin


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


# ---------------------------------------------------------------------------
# Pydantic request / response schemas
# ---------------------------------------------------------------------------


class ListCreate(TerminalBase):
    name: str
    type: ListType
    color: str | None = None
    source_list_ids: list[str] | None = None


class ListPublic(TerminalBase):
    id: str
    user_id: str
    name: str
    type: ListType
    color: str | None = None
    symbols: list[str] = []
    source_list_ids: list[str] = []


class ListUpdate(TerminalBase):
    name: str | None = None
    color: str | None = None


class SymbolsUpdate(TerminalBase):
    symbols: list[str]


class SourceListsUpdate(TerminalBase):
    source_list_ids: list[str]
