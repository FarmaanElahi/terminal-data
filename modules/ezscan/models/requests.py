from typing import List, Optional, Literal
from pydantic import BaseModel, validator


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
        sort_by: Column name to sort results by
        version: API version
    """
    conditions: List[Condition]
    columns: List[ColumnDef]
    logic: Literal["and", "or"] = "and"
    sort_by: Optional[str] = None
    version: Literal["v1"] = "v1"
