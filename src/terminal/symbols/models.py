from typing import Any
from sqlmodel import Field, Column
from sqlalchemy import Computed, Index
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from terminal.models import PrimaryKeyModel, TimeStampMixin, TerminalBase


class Symbol(PrimaryKeyModel, TimeStampMixin, table=True):
    """
    Symbol model for storing ticker information with Full-Text Search.
    """

    __tablename__ = "symbols"

    ticker: str = Field(index=True, unique=True)
    name: str = Field(index=True)
    type: str = Field(index=True)  # stock, fund, etc.
    market: str = Field(index=True)  # india, america, etc.
    isin: str | None = Field(default=None, index=True)

    # Store list of indexes (e.g., [{"name": "Nifty 50", "proname": "NSE:NIFTY"}])
    indexes: list[dict[str, str]] = Field(
        default_factory=list,
        sa_column=Column(JSONB),
    )

    # Store list of strings (e.g., ["common"])
    typespecs: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSONB),
    )

    # Full-Text Search Vector
    # Automatically updated when ticker or name changes
    # Postgres specific: GENERATED ALWAYS AS (to_tsvector('english', ticker || ' ' || name)) STORED
    search_vector: Any = Field(
        sa_column=Column(
            TSVECTOR,
            Computed(
                "to_tsvector('english', ticker || ' ' || name)",
                persisted=True,
            ),
        )
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
    ticker: str
    name: str
    type: str
    market: str
    isin: str | None
    indexes: list[dict[str, str]]
    typespecs: list[str]
