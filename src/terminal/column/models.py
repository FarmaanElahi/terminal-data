"""Models for the column module."""

from typing import Literal, Any

from pydantic import BaseModel
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from terminal.condition.models import TimeframeLiteral, TimeframeMode
from terminal.database.core import Base
from terminal.models import PrimaryKeyModel, TerminalBase, TimeStampMixin


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class ConditionDef(BaseModel):
    """Definition of a single condition within a ColumnSet."""

    name: str | None = None
    formula: str
    evaluate_as: Literal["true", "gt", "lt", "in_between", "rank"] | None = None
    evaluate_as_params: list[Any] | None = None


class ColumnDef(BaseModel):
    """Definition of a single column within a ColumnSet.

    Two column types:
      - ``value``: displays a computed or static value (field or formula)
      - ``condition``: evaluates one or more boolean conditions
    """

    # ── Core ──────────────────────────────────────────────────────────
    id: str
    name: str
    visible: bool = True
    type: Literal["value", "condition"]
    filter: Literal["active", "inactive", "off"] = "off"

    # ── Value Column ──────────────────────────────────────────────────
    value_type: Literal["field", "formula"] | None = None
    value_field_data_type: Literal["numeric", "string", "date"] | None = None
    value_formula: str | None = None
    value_formula_tf: TimeframeLiteral | None = "D"
    value_formula_x_bar_ago: int | None = None
    # value filter
    value_formula_filter_enabled: bool | None = None
    value_formula_filter_op: Literal["gt", "lt"] | None = None
    value_formula_filter_params: list[Any] | None = None
    value_formula_filter_evaluate_on: (
        Literal["now", "x_bar_ago", "within_x_bars", "x_bar_in_row"] | None
    ) = "now"
    value_formula_filter_evaluate_on_params: list[Any] | None = None
    value_formula_refresh_interval: int | None = None

    # ── Condition Column ──────────────────────────────────────────────
    conditions: list[ConditionDef] | None = None
    conditions_logic: Literal["and", "or"] | None = None
    condition_tf_mode: TimeframeMode | None = None
    conditions_tf: TimeframeLiteral | None = "D"
    condition_value_x_bar_ago: int | None = None

    # ── Display ───────────────────────────────────────────────────────
    display_color: str | None = None
    display_column_width: int | None = None
    sort: Literal["asc", "desc"] | None = None
    display_numeric_positive_color: str | None = None
    display_numeric_negative_color: str | None = None
    display_numeric_prefix: str | None = None
    display_numeric_suffix: str | None = None
    display_numeric_show_positive_sign: bool | None = None


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
