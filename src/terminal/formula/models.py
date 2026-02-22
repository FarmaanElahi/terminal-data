"""Models for the formula module."""

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from terminal.database.core import Base
from terminal.models import PrimaryKeyModel, TerminalBase, TimeStampMixin


class Formula(Base, PrimaryKeyModel, TimeStampMixin):
    """User-defined formula function.

    Users save parameterized formulas as named functions that can be
    referenced in other formulas by ID.  The ``name`` is a display label
    (editable without breaking references).
    """

    __tablename__ = "user_formulas"

    user_id: Mapped[str] = mapped_column(index=True)
    name: Mapped[str]  # display name, e.g. "PriceAVGCom"
    body: Mapped[str]  # expression body, e.g. "C / SMA(C, d) > threshold"
    params: Mapped[dict] = mapped_column(
        JSONB, default=dict
    )  # {"D": 10.0, "THRESHOLD": 1.2}


class FormulaCreate(TerminalBase):
    """Schema for creating a user-defined formula."""

    name: str
    formula: str  # multi-line raw formula (with param lines)


class FormulaPublic(TerminalBase):
    """Schema for returning a user-defined formula."""

    id: str
    name: str
    body: str
    params: dict[str, float]


class FormulaValidateRequest(TerminalBase):
    """Schema for validating a formula against a symbol."""

    formula: str
    symbol: str


class FormulaValidateResponse(TerminalBase):
    """Schema for the formula validation result."""

    valid: bool
    formula: str
    symbol: str
    result_type: str | None = None  # "bool" or "float"
    last_value: float | bool | None = None
    rows: int | None = None
    error: str | None = None
