"""Alert CRUD service — database operations for alerts, logs, and channels."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select, func, desc
from sqlalchemy.orm import Session

from terminal.alerts.models import (
    Alert,
    AlertCreate,
    AlertLog,
    AlertUpdate,
    UserNotificationChannel,
    NotificationChannelCreate,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# Alert CRUD
# ═══════════════════════════════════════════════════════════════════════════


def create_alert(session: Session, user_id: str, data: AlertCreate) -> Alert:
    """Create a new alert."""
    alert = Alert(
        user_id=user_id,
        name=data.name,
        symbol=data.symbol,
        alert_type=data.alert_type,
        status="active",
        trigger_condition=data.trigger_condition,
        guard_conditions=[g.model_dump() for g in data.guard_conditions],
        frequency=data.frequency,
        frequency_interval=data.frequency_interval,
        expiry=data.expiry,
        notification_channels=data.notification_channels,
        drawing_id=data.drawing_id,
    )
    session.add(alert)
    session.flush()
    session.refresh(alert)
    return alert


def get_alert(session: Session, alert_id: str, user_id: str) -> Alert | None:
    """Get an alert by ID, scoped to user."""
    return (
        session.execute(
            select(Alert).where(Alert.id == alert_id, Alert.user_id == user_id)
        )
        .scalars()
        .first()
    )


def list_alerts(
    session: Session,
    user_id: str,
    *,
    status: str | None = None,
    symbol: str | None = None,
) -> list[Alert]:
    """List alerts for a user, optionally filtered by status or symbol."""
    query = select(Alert).where(Alert.user_id == user_id)
    if status:
        query = query.where(Alert.status == status)
    if symbol:
        query = query.where(Alert.symbol == symbol)
    query = query.order_by(desc(Alert.created_at))
    return list(session.execute(query).scalars().all())


def update_alert(session: Session, alert: Alert, data: AlertUpdate) -> Alert:
    """Update an alert with the provided fields."""
    update_data = data.model_dump(exclude_unset=True)

    # Handle guard_conditions serialization
    if "guard_conditions" in update_data and update_data["guard_conditions"] is not None:
        update_data["guard_conditions"] = [
            g if isinstance(g, dict) else g.model_dump()
            for g in data.guard_conditions
        ]

    for key, value in update_data.items():
        setattr(alert, key, value)

    session.add(alert)
    session.flush()
    session.refresh(alert)
    return alert


def delete_alert(session: Session, alert: Alert) -> None:
    """Delete an alert and its logs (CASCADE)."""
    session.delete(alert)
    session.flush()


def delete_alerts_by_drawing(
    session: Session, user_id: str, drawing_id: str
) -> int:
    """Delete all alerts linked to a specific drawing. Returns count deleted."""
    alerts = (
        session.execute(
            select(Alert).where(
                Alert.user_id == user_id, Alert.drawing_id == drawing_id
            )
        )
        .scalars()
        .all()
    )
    count = 0
    for alert in alerts:
        session.delete(alert)
        count += 1
    session.flush()
    return count


def set_alert_status(session: Session, alert: Alert, status: str) -> Alert:
    """Change alert status (active, paused, triggered, expired)."""
    alert.status = status
    session.add(alert)
    session.flush()
    session.refresh(alert)
    return alert


def record_trigger(
    session: Session, alert: Alert, trigger_value: float | None, message: str
) -> AlertLog:
    """Record that an alert was triggered and update its state."""
    now = datetime.now(timezone.utc)

    # Create log entry
    log = AlertLog(
        alert_id=alert.id,
        user_id=alert.user_id,
        symbol=alert.symbol,
        triggered_at=now,
        trigger_value=trigger_value,
        message=message,
    )
    session.add(log)

    # Update alert state
    alert.trigger_count += 1
    alert.last_triggered_at = now

    # Auto-deactivate "once" alerts
    if alert.frequency == "once":
        alert.status = "triggered"

    session.add(alert)
    session.flush()
    session.refresh(log)
    return log


def get_active_alerts_by_symbol(session: Session) -> dict[str, list[Alert]]:
    """Load all active alerts grouped by symbol. Used by the engine on startup."""
    alerts = (
        session.execute(select(Alert).where(Alert.status == "active"))
        .scalars()
        .all()
    )
    index: dict[str, list[Alert]] = {}
    for alert in alerts:
        index.setdefault(alert.symbol, []).append(alert)
    return index


# ═══════════════════════════════════════════════════════════════════════════
# Alert Log queries
# ═══════════════════════════════════════════════════════════════════════════


def list_alert_logs(
    session: Session,
    user_id: str,
    *,
    alert_id: str | None = None,
    symbol: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[AlertLog], int]:
    """Query alert logs with pagination. Returns (logs, total_count)."""
    query = select(AlertLog).where(AlertLog.user_id == user_id)
    count_query = select(func.count(AlertLog.id)).where(AlertLog.user_id == user_id)

    if alert_id:
        query = query.where(AlertLog.alert_id == alert_id)
        count_query = count_query.where(AlertLog.alert_id == alert_id)
    if symbol:
        query = query.where(AlertLog.symbol == symbol)
        count_query = count_query.where(AlertLog.symbol == symbol)

    total = session.execute(count_query).scalar() or 0
    logs = list(
        session.execute(
            query.order_by(desc(AlertLog.triggered_at)).limit(limit).offset(offset)
        )
        .scalars()
        .all()
    )
    return logs, total


def mark_logs_read(session: Session, user_id: str, log_ids: list[str]) -> int:
    """Mark alert logs as read. Returns count updated."""
    count = 0
    for log_id in log_ids:
        log = session.execute(
            select(AlertLog).where(
                AlertLog.id == log_id, AlertLog.user_id == user_id
            )
        ).scalars().first()
        if log and not log.read:
            log.read = True
            session.add(log)
            count += 1
    session.flush()
    return count


# ═══════════════════════════════════════════════════════════════════════════
# Notification Channel CRUD
# ═══════════════════════════════════════════════════════════════════════════


def create_channel(
    session: Session, user_id: str, data: NotificationChannelCreate
) -> UserNotificationChannel:
    """Create a notification channel for a user."""
    channel = UserNotificationChannel(
        user_id=user_id,
        channel_type=data.channel_type,
        config=data.config,
    )
    session.add(channel)
    session.flush()
    session.refresh(channel)
    return channel


def list_channels(session: Session, user_id: str) -> list[UserNotificationChannel]:
    """List all notification channels for a user."""
    return list(
        session.execute(
            select(UserNotificationChannel).where(
                UserNotificationChannel.user_id == user_id
            )
        )
        .scalars()
        .all()
    )


def get_channel(
    session: Session, channel_id: str, user_id: str
) -> UserNotificationChannel | None:
    """Get a notification channel by ID."""
    return (
        session.execute(
            select(UserNotificationChannel).where(
                UserNotificationChannel.id == channel_id,
                UserNotificationChannel.user_id == user_id,
            )
        )
        .scalars()
        .first()
    )


def delete_channel(session: Session, channel: UserNotificationChannel) -> None:
    """Delete a notification channel."""
    session.delete(channel)
    session.flush()


def get_channels_by_ids(
    session: Session, channel_ids: list[str]
) -> list[UserNotificationChannel]:
    """Fetch channels by their IDs (for notification dispatch)."""
    if not channel_ids:
        return []
    return list(
        session.execute(
            select(UserNotificationChannel).where(
                UserNotificationChannel.id.in_(channel_ids),
                UserNotificationChannel.is_active == True,  # noqa: E712
            )
        )
        .scalars()
        .all()
    )
