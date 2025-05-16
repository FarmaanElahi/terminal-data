from datetime import datetime
from typing import Optional, Literal

from pydantic import BaseModel


class TrendlinePoint(BaseModel):
    timestamp: datetime
    price: float


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
    rhs_attr: dict  # We'll parse this further depending on rhs_type
    last_triggered_at: datetime | None = None
    last_triggered_price: float | None = None

    def is_trendline(self) -> bool:
        return self.rhs_type == "trend_line"

    def get_constant_value(self) -> Optional[float]:
        if self.rhs_type == "constant":
            return self.rhs_attr.get("constant")
        return None

    def get_trendline_points(self) -> Optional[list[TrendlinePoint]]:
        if self.rhs_type == "trend_line":
            try:
                points = self.rhs_attr.get("trend_line", [])
                return [TrendlinePoint(**p) for p in points]
            except Exception:
                return None
        return None


class ChangeUpdate(BaseModel):
    symbol: str
    ltq: float
    ltp: float
    ltt: datetime
