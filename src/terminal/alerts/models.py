"""Alert system models — SQLAlchemy tables + Pydantic schemas.

Tables:
  - Alert          – core alert definitions (formula or drawing-based)
  - AlertLog       – persistent trigger history
  - UserNotificationChannel – per-user notification provider config
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import DateTime, ForeignKey, String, Text, Boolean, Integer, Float
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from terminal.database.core import Base
from terminal.models import PrimaryKeyModel, TerminalBase, TimeStampMixin


# ---------------------------------------------------------------------------
# Literal types
# ---------------------------------------------------------------------------

AlertType = Literal["formula", "drawing"]
AlertStatus = Literal["active", "paused", "triggered", "expired"]
AlertFrequency = Literal["once", "once_per_minute", "once_per_bar", "end_of_day"]
DrawingTrigger = Literal[
    "crosses_above", "crosses_below",
    "enters", "exits", "enters_or_exits",
]
ChannelType = Literal["in_app", "telegram", "web_push"]


# ═══════════════════════════════════════════════════════════════════════════
# SQLAlchemy models
# ═══════════════════════════════════════════════════════════════════════════


class Alert(Base, PrimaryKeyModel, TimeStampMixin):
    """Core alert definition.

    ``trigger_condition`` stores the primary condition as JSONB:
      - Formula: ``{"formula": "close > 1500"}``
      - Drawing: ``{"drawing_type": "trendline", "trigger_when": "crosses_above",
                     "points": [{"time": 1733788800, "price": 1450.0}, ...]}``
    """

    __tablename__ = "alerts"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String, default="")
    symbol: Mapped[str] = mapped_column(String, index=True)

    alert_type: Mapped[str] = mapped_column(String, default="formula")  # formula | drawing
    status: Mapped[str] = mapped_column(String, default="active", index=True)

    # Primary trigger condition (JSONB)
    trigger_condition: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Additional formula guard conditions (all must be true for trigger to fire)
    guard_conditions: Mapped[list] = mapped_column(JSONB, default=list)

    # Frequency settings
    frequency: Mapped[str] = mapped_column(String, default="once")
    frequency_interval: Mapped[int] = mapped_column(Integer, default=60)  # seconds

    # Expiry
    expiry: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    # Trigger tracking
    trigger_count: Mapped[int] = mapped_column(Integer, default=0)
    last_triggered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    # Per-alert notification channels — list of channel IDs or null (log-only)
    notification_channels: Mapped[list | None] = mapped_column(
        JSONB, nullable=True, default=None
    )

    # TradingView drawing ID — links alert to a chart drawing
    drawing_id: Mapped[str | None] = mapped_column(
        String, nullable=True, default=None, index=True
    )


class AlertLog(Base, PrimaryKeyModel):
    """Persistent trigger history — one row per alert fire."""

    __tablename__ = "alert_logs"

    alert_id: Mapped[str] = mapped_column(
        ForeignKey("alerts.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str] = mapped_column(String, index=True)
    symbol: Mapped[str] = mapped_column(String)
    triggered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    trigger_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    message: Mapped[str] = mapped_column(Text, default="")
    read: Mapped[bool] = mapped_column(Boolean, default=False)


class UserNotificationChannel(Base, PrimaryKeyModel, TimeStampMixin):
    """Per-user notification provider configuration."""

    __tablename__ = "user_notification_channels"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    channel_type: Mapped[str] = mapped_column(String)  # in_app | telegram | web_push
    config: Mapped[dict] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


# ═══════════════════════════════════════════════════════════════════════════
# Pydantic schemas
# ═══════════════════════════════════════════════════════════════════════════


# -- Drawing sub-schemas ---------------------------------------------------

class DrawingPoint(BaseModel):
    """A single anchor point on a drawing (time in Unix seconds, price)."""
    time: int
    price: float


class TrendlineCondition(BaseModel):
    drawing_type: Literal["trendline"] = "trendline"
    trigger_when: Literal["crosses_above", "crosses_below"]
    points: list[DrawingPoint]  # exactly 2 points


class HlineCondition(BaseModel):
    drawing_type: Literal["hline"] = "hline"
    trigger_when: Literal["crosses_above", "crosses_below"]
    price: float


class RectangleCondition(BaseModel):
    drawing_type: Literal["rectangle"] = "rectangle"
    trigger_when: Literal["enters", "exits", "enters_or_exits"]
    top: float
    bottom: float
    left: int   # Unix seconds
    right: int  # Unix seconds


class FormulaCondition(BaseModel):
    formula: str


# -- Guard condition -------------------------------------------------------

class GuardCondition(BaseModel):
    """An additional formula guard that must be true for the alert to fire."""
    formula: str


# -- Alert CRUD schemas ----------------------------------------------------

class AlertCreate(TerminalBase):
    """Request body for creating an alert."""
    name: str = ""
    symbol: str
    alert_type: AlertType = "formula"
    trigger_condition: dict  # FormulaCondition | TrendlineCondition | HlineCondition | RectangleCondition
    guard_conditions: list[GuardCondition] = Field(default_factory=list)
    frequency: AlertFrequency = "once"
    frequency_interval: int = 60  # seconds
    expiry: datetime | None = None
    notification_channels: list[str] | None = None  # channel IDs or null
    drawing_id: str | None = None


class AlertUpdate(TerminalBase):
    """Request body for updating an alert."""
    name: str | None = None
    trigger_condition: dict | None = None
    guard_conditions: list[GuardCondition] | None = None
    frequency: AlertFrequency | None = None
    frequency_interval: int | None = None
    expiry: datetime | None = None
    notification_channels: list[str] | None = None
    drawing_id: str | None = None


class AlertPublic(TerminalBase):
    """Alert response schema."""
    id: str
    user_id: str
    name: str
    symbol: str
    alert_type: str
    status: str
    trigger_condition: dict
    guard_conditions: list[dict]
    frequency: str
    frequency_interval: int
    expiry: datetime | None = None
    trigger_count: int
    last_triggered_at: datetime | None = None
    notification_channels: list[str] | None = None
    drawing_id: str | None = None
    created_at: datetime
    updated_at: datetime


class AlertLogPublic(TerminalBase):
    """Alert log response schema."""
    id: str
    alert_id: str
    user_id: str
    symbol: str
    triggered_at: datetime
    trigger_value: float | None = None
    message: str
    read: bool


# -- Notification channel schemas ------------------------------------------

class NotificationChannelCreate(TerminalBase):
    channel_type: ChannelType
    config: dict = Field(default_factory=dict)


class NotificationChannelPublic(TerminalBase):
    id: str
    user_id: str
    channel_type: str
    config: dict
    is_active: bool
    created_at: datetime
    updated_at: datetime
