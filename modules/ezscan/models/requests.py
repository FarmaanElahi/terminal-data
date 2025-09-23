from typing import List, Optional, Literal

from pydantic import BaseModel, model_validator


class SortColumn(BaseModel):
    """Defines a column to sort by with direction."""
    column: str
    direction: Literal["asc", "desc"] = "desc"


class Condition(BaseModel):
    """Represents a technical analysis condition."""
    expression: str
    evaluation_period: Optional[Literal["now", "x_bar_ago", "within_last", "in_row"]] = "now"
    evaluation_type: Literal["boolean", "rank"] = "boolean"
    value: Optional[int] = None
    condition_type: Literal["computed", "static"] = "computed"
    rank_min: Optional[int] = None
    rank_max: Optional[int] = None

    def check_evaluation_period(cls, v, info):
        values = info.data
        condition_type = values.get("condition_type")
        evaluation_type = values.get("evaluation_type")

        if condition_type == "computed" and v is None:
            return "now"
        if condition_type == "static" and v is not None:
            raise ValueError("evaluation_period not allowed for static conditions")
        if evaluation_type == "rank" and v != "now":
            raise ValueError("rank evaluation only supports 'now' evaluation_period")
        return v

    @classmethod
    def check_value(cls, v, info):
        values = info.data
        condition_type = values.get("condition_type")
        ep = values.get("evaluation_period")
        evaluation_type = values.get("evaluation_type")

        if evaluation_type == "rank":
            # For rank evaluation, value is not used
            if v is not None:
                raise ValueError("value not allowed for rank evaluation")
            return v

        if condition_type == "computed":
            if ep in ["x_bar_ago", "within_last", "in_row"] and (v is None or v <= 0):
                raise ValueError("value must be positive integer for this evaluation_period")
            if ep == "now" and v is not None:
                raise ValueError("value not allowed for 'now'")
        elif condition_type == "static" and v is not None:
            raise ValueError("value not allowed for static conditions")
        return v

    @model_validator(mode='after')
    def check_rank_fields(self):
        if self.evaluation_type == "rank":
            # Set defaults for rank fields
            if self.rank_min is None:
                self.rank_min = 1
            if self.rank_max is None:
                self.rank_max = 99

            # Validate rank range
            if self.rank_min < 1 or self.rank_min > 100:
                raise ValueError("rank_min must be between 1 and 100")
            if self.rank_max < 1 or self.rank_max > 100:
                raise ValueError("rank_max must be between 1 and 100")
            if self.rank_max < self.rank_min:
                raise ValueError("rank_max must be >= rank_min")
        else:
            # Clear rank fields for non-rank conditions
            self.rank_min = None
            self.rank_max = None

        return self


class ColumnDef(BaseModel):
    """Defines an output column for scan results."""
    id: str
    name: str
    type: Literal["static", "computed", "condition"]
    property_name: Optional[str] = None
    expression: Optional[str] = None
    conditions: Optional[List[Condition]] = None
    logic: Optional[Literal["and", "or"]] = "and"

    @classmethod
    def check_static_column(cls, v, info):
        values = info.data
        if values.get("type") == "static" and not v:
            raise ValueError("property_name is required for static columns")
        return v

    @classmethod
    def check_computed_column(cls, v, info):
        values = info.data
        if values.get("type") == "computed" and not v:
            raise ValueError("expression is required for computed columns")
        return v

    @classmethod
    def check_condition_column(cls, v, info):
        values = info.data
        if values.get("type") == "condition" and (not v or len(v) == 0):
            raise ValueError("conditions list is required for condition columns")
        return v


class ScanRequest(BaseModel):
    """Complete scan request specification."""
    conditions: List[Condition]
    columns: List[ColumnDef]
    logic: Literal["and", "or"] = "and"
    sort_columns: Optional[List[SortColumn]] = None
    market: Literal["india", "us"] = "india"

    @classmethod
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