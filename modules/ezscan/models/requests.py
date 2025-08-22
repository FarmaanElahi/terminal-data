from typing import List, Optional, Literal

from pydantic import BaseModel, validator


class SortColumn(BaseModel):
    """
    Defines a column to sort by with direction.

    Attributes:
        column: Column name to sort by
        direction: Sort direction ('asc' or 'desc')
    """
    column: str
    direction: Literal["asc", "desc"] = "desc"


class Condition(BaseModel):
    """
    Represents a technical analysis condition.

    Attributes:
        condition: Technical expression (e.g., 'c > sma(c, 20)')
        evaluation_period: When to evaluate ('now', 'x_bar_ago', 'within_last', 'in_row')
        value: Period value for time-based evaluations
    """
    condition: str
    evaluation_period: Literal["now", "x_bar_ago", "within_last", "in_row"]
    value: Optional[int] = None

    @validator("value", always=True)
    def check_value(cls, v, values):
        ep = values.get("evaluation_period")
        if ep in ["x_bar_ago", "within_last", "in_row"] and (v is None or v <= 0):
            raise ValueError(
                "value must be positive integer for this evaluation_period"
            )
        if ep == "now" and v is not None:
            raise ValueError("value not allowed for 'now'")
        return v


class ColumnDef(BaseModel):
    """
    Defines an output column for scan results.

    Attributes:
        name: Column name in output
        type: Column type ('evaluated' for technical expressions, 'fixed' for metadata)
        value: Technical expression for evaluated columns
        prop: Metadata property name for fixed columns
    """
    name: str
    type: Literal["evaluated", "fixed"]
    value: Optional[str] = None  # For evaluated columns
    prop: Optional[str] = None  # For fixed columns


class ScanRequest(BaseModel):
    """
    Complete scan request specification.

    Attributes:
        conditions: List of technical conditions
        columns: List of output column definitions
        logic: How to combine conditions ('and' or 'or')
        sort_columns: List of columns to sort by with direction (new)
    """
    conditions: List[Condition]
    columns: List[ColumnDef]
    logic: Literal["and", "or"] = "and"
    sort_columns: Optional[List[SortColumn]] = None  # New multi-column sort

    def validate_sort_columns(cls, v, values):
        """Ensure either sort_by or sort_columns is used, not both."""
        sort_by = values.get("sort_by")

        if sort_by is not None and v is not None:
            raise ValueError("Cannot use both 'sort_by' and 'sort_columns'. Use 'sort_columns' for new implementations.")

        # Convert legacy sort_by to sort_columns format
        if sort_by is not None and v is None:
            v = [SortColumn(column=sort_by, direction="desc")]

        return v
