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
        expression: Technical expression (e.g., 'c > sma(c, 20)' or 'opm > 15')
        evaluation_period: When to evaluate ('now', 'x_bar_ago', 'within_last', 'in_row') - only for computed conditions
        value: Period value for time-based evaluations - only for computed conditions
        condition_type: Type of condition ('computed' or 'static')
    """
    expression: str
    evaluation_period: Optional[Literal["now", "x_bar_ago", "within_last", "in_row"]] = None
    value: Optional[int] = None
    condition_type: Literal["computed", "static"] = "computed"

    # #@validator("evaluation_period", always=True)
    def check_evaluation_period(cls, v, values):
        condition_type = values.get("condition_type")

        if condition_type == "computed" and v is None:
            # For computed conditions, evaluation_period is required
            return "now"  # Default to "now"
        elif condition_type == "static" and v is not None:
            # For static conditions, evaluation_period should not be used
            raise ValueError("evaluation_period not allowed for static conditions")

        return v

    # #@validator("value", always=True)
    def check_value(cls, v, values):
        condition_type = values.get("condition_type")
        ep = values.get("evaluation_period")

        # Only validate for computed conditions
        if condition_type == "computed":
            if ep in ["x_bar_ago", "within_last", "in_row"] and (v is None or v <= 0):
                raise ValueError(
                    "value must be positive integer for this evaluation_period"
                )
            if ep == "now" and v is not None:
                raise ValueError("value not allowed for 'now'")
        elif condition_type == "static" and v is not None:
            raise ValueError("value not allowed for static conditions")

        return v


class ColumnDef(BaseModel):
    """
    Defines an output column for scan results.

    Attributes:
        id: Unique identifier for the column
        name: Column name in output
        type: Column type ('static', 'computed', 'condition')
        property_name: Metadata property name for static columns
        expression: Expression for computed columns
        conditions: List of Condition objects for condition columns
        logic: Logic operator for multiple conditions in condition columns ('and' or 'or')
    """
    id: str
    name: str
    type: Literal["static", "computed", "condition"]

    # For static columns
    property_name: Optional[str] = None

    # For computed columns
    expression: Optional[str] = None

    # For condition columns
    conditions: Optional[List[Condition]] = None
    logic: Optional[Literal["and", "or"]] = "and"

    #@validator("property_name", always=True)
    def check_static_column(cls, v, values):
        if values.get("type") == "static" and not v:
            raise ValueError("property_name is required for static columns")
        return v

    #@validator("expression", always=True)
    def check_computed_column(cls, v, values):
        if values.get("type") == "computed" and not v:
            raise ValueError("expression is required for computed columns")
        return v

    #@validator("conditions", always=True)
    def check_condition_column(cls, v, values):
        if values.get("type") == "condition" and (not v or len(v) == 0):
            raise ValueError("conditions list is required for condition columns")
        return v


class ScanRequest(BaseModel):
    """
    Complete scan request specification.

    Attributes:
        conditions: List of technical conditions
        columns: List of output column definitions
        logic: How to combine conditions ('and' or 'or')
        sort_columns: List of columns to sort by with direction
    """
    conditions: List[Condition]
    columns: List[ColumnDef]
    logic: Literal["and", "or"] = "and"
    sort_columns: Optional[List[SortColumn]] = None

    #@validator("columns")
    def check_unique_column_ids(cls, v):
        """Ensure column IDs are unique."""
        ids = [col.id for col in v]
        if len(ids) != len(set(ids)):
            raise ValueError("Column IDs must be unique")
        return v