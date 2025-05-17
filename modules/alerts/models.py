from datetime import datetime, timezone
from typing import Optional, Literal

from pydantic import BaseModel, field_validator


class Point(BaseModel):
    time: datetime
    price: float

    @classmethod
    @field_validator('time', mode='before')
    def parse_timestamp_seconds(cls, value):
        return datetime.fromtimestamp(value, tz=timezone.utc) if isinstance(value, (int, float)) else value


class RHSAttr(BaseModel):
    constant: int | float | None = None
    trend_line: list[Point] | None = None


class Alert(BaseModel):
    id: str
    created_at: datetime
    updated_at: datetime | None
    deleted_at: datetime | None
    notes: str | None
    is_active: bool
    user_id: str
    symbol: str
    type: Literal["simple"]  # Currently fixed to "simple"
    lhs_type: Literal["last_price"]
    lhs_attr: dict | None  # Reserved for future flexibility
    operator: Literal["<", "<=", ">", ">=", "==", "!="]
    rhs_type: Literal["constant", "trend_line"]
    rhs_attr: RHSAttr
    last_triggered_at: datetime | None = None
    last_triggered_price: float | None = None

    def is_trendline(self) -> bool:
        return self.rhs_type == "trend_line"

    def get_constant_value(self) -> Optional[float]:
        if self.rhs_type == "constant":
            return self.rhs_attr.get("constant")
        return None

    def get_trendline_points(self) -> Optional[list[Point]]:
        return self.rhs_attr.trend_line


class ChangeUpdate(BaseModel):
    symbol: str
    ltq: float
    ltp: float
    ltt: datetime
