"""Alert REST API — full CRUD for local alerts, logs, and drawing-linked operations."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from terminal.alerts import service as alerts_service
from terminal.alerts.models import (
    AlertCreate,
    AlertLogPublic,
    AlertPublic,
    AlertUpdate,
)
from terminal.auth.models import User
from terminal.auth.router import get_current_user
from terminal.dependencies import get_alert_engine, get_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/alerts", tags=["Alerts"])


# ══════════════════════════════════════════════════════════════════════
# IMPORTANT: Static paths (/logs, /by-drawing) MUST be registered
# BEFORE dynamic /{alert_id} paths, otherwise FastAPI matches "logs"
# and "by-drawing" as alert_id values.
# ══════════════════════════════════════════════════════════════════════


# ── Alert Logs (static paths first!) ─────────────────────────────────


@router.get("/logs", response_model=dict)
def list_alert_logs(
    alert_id: str | None = Query(None),
    symbol: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    """Query alert trigger logs with pagination."""
    logs, total = alerts_service.list_alert_logs(
        session,
        current_user.id,
        alert_id=alert_id,
        symbol=symbol,
        limit=limit,
        offset=offset,
    )
    return {
        "logs": [AlertLogPublic.model_validate(log) for log in logs],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.post("/logs/read")
def mark_logs_read(
    log_ids: list[str],
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, int]:
    """Mark alert logs as read."""
    count = alerts_service.mark_logs_read(session, current_user.id, log_ids)
    return {"marked_read": count}


@router.delete("/logs")
def clear_alert_logs(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, int]:
    """Clear all alert logs for the current user."""
    count = alerts_service.clear_alert_logs(session, current_user.id)
    return {"deleted": count}


@router.delete("/logs/{log_id}")
def delete_alert_log(
    log_id: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, bool]:
    """Delete a specific alert log."""
    success = alerts_service.delete_alert_log(session, current_user.id, log_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Log not found"
        )
    return {"success": success}


# ── Drawing-linked operations (static path) ──────────────────────────


@router.delete("/by-drawing/{drawing_id}")
def delete_alerts_by_drawing(
    drawing_id: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
    engine=Depends(get_alert_engine),
) -> dict[str, int]:
    """Delete all alerts linked to a TradingView drawing."""
    # Remove from engine index
    if engine:
        engine.remove_alerts_by_drawing(drawing_id)

    count = alerts_service.delete_alerts_by_drawing(
        session, current_user.id, drawing_id
    )
    return {"deleted": count}


# ── Alert CRUD (dynamic paths last) ──────────────────────────────────


@router.get("", response_model=list[AlertPublic])
def list_alerts(
    status_filter: str | None = Query(None, alias="status"),
    symbol: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[AlertPublic]:
    """List alerts for the current user, optionally filtered."""
    alerts = alerts_service.list_alerts(
        session, current_user.id, status=status_filter, symbol=symbol
    )
    return [AlertPublic.model_validate(a) for a in alerts]


@router.post("", response_model=AlertPublic, status_code=status.HTTP_201_CREATED)
def create_alert(
    body: AlertCreate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
    engine=Depends(get_alert_engine),
) -> AlertPublic:
    """Create a new alert."""
    alert = alerts_service.create_alert(session, current_user.id, body)

    # Sync to engine in-memory index
    if engine:
        engine.add_alert(alert)

    return AlertPublic.model_validate(alert)


@router.put("/{alert_id}", response_model=AlertPublic)
def update_alert(
    alert_id: str,
    body: AlertUpdate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
    engine=Depends(get_alert_engine),
) -> AlertPublic:
    """Update an alert's conditions, frequency, channels, etc."""
    alert = alerts_service.get_alert(session, alert_id, current_user.id)
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found"
        )
    alert = alerts_service.update_alert(session, alert, body)

    # Sync to engine
    if engine:
        engine.update_alert(alert)

    return AlertPublic.model_validate(alert)


@router.delete("/{alert_id}")
def delete_alert(
    alert_id: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
    engine=Depends(get_alert_engine),
) -> dict[str, str]:
    """Delete an alert."""
    alert = alerts_service.get_alert(session, alert_id, current_user.id)
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found"
        )

    # Remove from engine index
    if engine:
        engine.remove_alert(alert_id)

    alerts_service.delete_alert(session, alert)
    return {"status": "deleted"}


@router.post("/{alert_id}/activate", response_model=AlertPublic)
def activate_alert(
    alert_id: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
    engine=Depends(get_alert_engine),
) -> AlertPublic:
    """Re-activate a paused or triggered alert."""
    alert = alerts_service.get_alert(session, alert_id, current_user.id)
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found"
        )
    if alert.status == "active":
        return AlertPublic.model_validate(alert)

    alert = alerts_service.set_alert_status(session, alert, "active")

    # Sync to engine
    if engine:
        engine.update_alert(alert)

    return AlertPublic.model_validate(alert)


@router.post("/{alert_id}/pause", response_model=AlertPublic)
def pause_alert(
    alert_id: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
    engine=Depends(get_alert_engine),
) -> AlertPublic:
    """Pause an active alert."""
    alert = alerts_service.get_alert(session, alert_id, current_user.id)
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found"
        )
    if alert.status == "paused":
        return AlertPublic.model_validate(alert)

    alert = alerts_service.set_alert_status(session, alert, "paused")

    # Remove from engine (paused alerts don't evaluate)
    if engine:
        engine.update_alert(alert)

    return AlertPublic.model_validate(alert)
