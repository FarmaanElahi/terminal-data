from typing import List, Optional, Literal
from pydantic import BaseModel, validator


class SortColumn(BaseModel):
    """Defines a column to sort by with direction."""
    column: str
    direction: Literal["asc", "desc"] = "desc"


class Condition(BaseModel):
    """Represents a technical analysis condition."""
    expression: str
    evaluation_period: Optional[Literal["now", "x_bar_ago", "within_last", "in_row"]] = "now"
    value: Optional[int] = None
    condition_type: Literal["computed", "static"] = "computed"

    #@validator("evaluation_period")
    def check_evaluation_period(cls, v, values):
        condition_type = values.get("condition_type")
        if condition_type == "computed" and v is None:
            return "now"
        if condition_type == "static" and v is not None:
            raise ValueError("evaluation_period not allowed for static conditions")
        return v

    #@validator("value")
    def check_value(cls, v, values):
        condition_type = values.get("condition_type")
        ep = values.get("evaluation_period")
        if condition_type == "computed":
            if ep in ["x_bar_ago", "within_last", "in_row"] and (v is None or v <= 0):
                raise ValueError("value must be positive integer for this evaluation_period")
            if ep == "now" and v is not None:
                raise ValueError("value not allowed for 'now'")
        elif condition_type == "static" and v is not None:
            raise ValueError("value not allowed for static conditions")
        return v


class ColumnDef(BaseModel):
    """Defines an output column for scan results."""
    id: str
    name: str
    type: Literal["static", "computed", "condition"]
    property_name: Optional[str] = None
    expression: Optional[str] = None
    conditions: Optional[List[Condition]] = None
    logic: Optional[Literal["and", "or"]] = "and"

    #@validator("property_name")
    def check_static_column(cls, v, values):
        if values.get("type") == "static" and not v:
            raise ValueError("property_name is required for static columns")
        return v

    #@validator("expression")
    def check_computed_column(cls, v, values):
        if values.get("type") == "computed" and not v:
            raise ValueError("expression is required for computed columns")
        return v

    #@validator("conditions")
    def check_condition_column(cls, v, values):
        if values.get("type") == "condition" and (not v or len(v) == 0):
            raise ValueError("conditions list is required for condition columns")
        return v


class ScanRequest(BaseModel):
    """Complete scan request specification."""
    conditions: List[Condition]
    columns: List[ColumnDef]
    logic: Literal["and", "or"] = "and"
    sort_columns: Optional[List[SortColumn]] = None

    #@validator("columns")
    def check_unique_column_ids(cls, v):
        ids = [col.id for col in v]
        if len(ids) != len(set(ids)):
            raise ValueError("Column IDs must be unique")
        return v


class ScanResponse(BaseModel):
    """Response model for scan results."""
    count: int
    columns: List[str]
    data: List[List]
    success: bool
