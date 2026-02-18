from typing import Any, List, Dict
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Computed, Index
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from terminal.models import Base, PrimaryKeyModel, TimeStampMixin, TerminalBase


class Symbol(Base, PrimaryKeyModel, TimeStampMixin):
    """
    Symbol model for storing ticker information with Full-Text Search.
    """

    __tablename__ = "symbols"

    ticker: Mapped[str] = mapped_column(index=True, unique=True)
    name: Mapped[str] = mapped_column(index=True)
    type: Mapped[str] = mapped_column(index=True)  # stock, fund, etc.
    market: Mapped[str] = mapped_column(index=True)  # india, america, etc.
    isin: Mapped[str | None] = mapped_column(default=None, index=True)

    # Store list of indexes (e.g., [{"name": "Nifty 50", "proname": "NSE:NIFTY"}])
    indexes: Mapped[List[Dict[str, str]]] = mapped_column(
        JSONB,
        default=list,
    )

    # Store list of strings (e.g., ["common"])
    typespecs: Mapped[List[str]] = mapped_column(
        JSONB,
        default=list,
    )

    # Full-Text Search Vector
    # Automatically updated when ticker or name changes
    # Postgres specific: GENERATED ALWAYS AS (to_tsvector('english', ticker || ' ' || name)) STORED
    search_vector: Mapped[Any] = mapped_column(
        TSVECTOR,
        Computed(
            "to_tsvector('english', ticker || ' ' || name)",
            persisted=True,
        ),
    )

    __table_args__ = (
        Index(
            "ix_symbols_search_vector_gin",
            "search_vector",
            postgresql_using="gin",
        ),
    )


class SymbolCreate(TerminalBase):
    ticker: str
    name: str
    type: str
    market: str
    isin: str | None = None
    indexes: list[dict[str, str]] = []
    typespecs: list[str] = []


class SymbolSearchResponse(TerminalBase):
    id: str
    ticker: str
    name: str
    type: str
    market: str
    isin: str | None
    indexes: list[dict[str, str]]
    typespecs: list[str]
