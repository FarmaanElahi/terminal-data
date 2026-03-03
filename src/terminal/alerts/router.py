import logging
from typing import Any

import httpx

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from terminal.alerts.models import (
    AlertCreateRequest,
    AlertDeleteRequest,
    AlertModifyRequest,
    AlertResponse,
)
from terminal.auth.models import User
from terminal.auth.router import get_current_user
from terminal.broker import service as broker_service
from terminal.broker.adapter import Capability
from terminal.broker.registry import broker_registry
from terminal.dependencies import get_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/alerts", tags=["Alerts"])


# ── Helpers ──────────────────────────────────────────────────────────


async def _resolve_provider_and_token(
    session: Session,
    user_id: str,
    provider_id: str,
) -> tuple[Any, str]:
    """Resolve the adapter and active token for a given provider_id."""
    adapter = broker_registry.get(provider_id)
    if adapter is None or not adapter.is_configured():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown or unconfigured provider: {provider_id}",
        )
    if not adapter.supports(Capability.ALERTS):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Provider {provider_id} does not support alerts",
        )

    credentials = broker_service.list_provider_credentials(
        session, user_id, provider_id
    )
    for credential in credentials:
        token = broker_service.get_credential_token(credential)
        if token and await adapter.validate_token(token):
            return adapter, token

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=f"No active valid credential for provider {provider_id}. Please log in.",
    )


def _to_alert_response(raw: dict, provider_id: str) -> AlertResponse:
    """Convert a raw Kite-style alert dict to our unified AlertResponse."""
    return AlertResponse(
        uuid=raw.get("uuid", ""),
        name=raw.get("name", ""),
        type=raw.get("type", "simple"),
        status=raw.get("status", ""),
        disabled_reason=raw.get("disabled_reason", ""),
        lhs_exchange=raw.get("lhs_exchange", ""),
        lhs_tradingsymbol=raw.get("lhs_tradingsymbol", ""),
        lhs_attribute=raw.get("lhs_attribute", "LastTradedPrice"),
        operator=raw.get("operator", ""),
        rhs_type=raw.get("rhs_type", "constant"),
        rhs_constant=raw.get("rhs_constant"),
        rhs_attribute=raw.get("rhs_attribute", ""),
        rhs_exchange=raw.get("rhs_exchange", ""),
        rhs_tradingsymbol=raw.get("rhs_tradingsymbol", ""),
        alert_count=raw.get("alert_count", 0),
        provider_id=provider_id,
        created_at=raw.get("created_at"),
        updated_at=raw.get("updated_at"),
    )


# ── Endpoints ────────────────────────────────────────────────────────


@router.get("", response_model=list[AlertResponse])
async def list_alerts(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[AlertResponse]:
    """List alerts from all connected alert-capable providers."""
    all_alerts: list[AlertResponse] = []

    for adapter in broker_registry.for_capability(Capability.ALERTS):
        credentials = broker_service.list_provider_credentials(
            session, current_user.id, adapter.provider_id
        )
        token: str | None = None
        for credential in credentials:
            t = broker_service.get_credential_token(credential)
            if t and await adapter.validate_token(t):
                token = t
                break

        if token is None:
            continue

        try:
            raw_alerts = await adapter.list_alerts(token)
            for raw in raw_alerts:
                all_alerts.append(_to_alert_response(raw, adapter.provider_id))
        except Exception:
            logger.exception(
                "Failed to list alerts from %s for user=%s",
                adapter.provider_id,
                current_user.id,
            )

    return all_alerts


@router.post("", response_model=AlertResponse)
async def create_alert(
    body: AlertCreateRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> AlertResponse:
    """Create an alert on the specified provider."""
    adapter, token = await _resolve_provider_and_token(
        session, current_user.id, body.provider_id
    )

    # Ensure name is never empty — Kite requires minimum 1 character
    name = body.name or f"{body.lhs_tradingsymbol} alert"

    logger.debug(
        "create_alert body: name=%r, lhs=%s:%s, operator=%s, rhs_type=%s, rhs_constant=%s",
        name,
        body.lhs_exchange,
        body.lhs_tradingsymbol,
        body.operator,
        body.rhs_type,
        body.rhs_constant,
    )

    params: dict[str, Any] = {
        "name": name,
        "type": body.type,
        "lhs_exchange": body.lhs_exchange,
        "lhs_tradingsymbol": body.lhs_tradingsymbol,
        "lhs_attribute": body.lhs_attribute,
        "operator": body.operator,
        "rhs_type": body.rhs_type,
    }
    if body.rhs_constant is not None:
        params["rhs_constant"] = body.rhs_constant
    if body.rhs_attribute:
        params["rhs_attribute"] = body.rhs_attribute
    if body.rhs_exchange:
        params["rhs_exchange"] = body.rhs_exchange
    if body.rhs_tradingsymbol:
        params["rhs_tradingsymbol"] = body.rhs_tradingsymbol

    try:
        raw = await adapter.create_alert(token, params)
    except httpx.HTTPStatusError as exc:
        # Extract Kite error message from response body
        try:
            err_body = exc.response.json()
            kite_msg = err_body.get("message", str(exc))
        except Exception:
            kite_msg = exc.response.text or str(exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Kite error: {kite_msg}",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to create alert: {exc}",
        )

    return _to_alert_response(raw, body.provider_id)


@router.put("/{alert_id}", response_model=AlertResponse)
async def modify_alert(
    alert_id: str,
    body: AlertModifyRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> AlertResponse:
    """Modify an alert on the specified provider."""
    adapter, token = await _resolve_provider_and_token(
        session, current_user.id, body.provider_id
    )

    params: dict[str, Any] = {}
    for field in (
        "name",
        "type",
        "lhs_exchange",
        "lhs_tradingsymbol",
        "lhs_attribute",
        "operator",
        "rhs_type",
        "rhs_constant",
        "rhs_attribute",
        "rhs_exchange",
        "rhs_tradingsymbol",
    ):
        value = getattr(body, field, None)
        if value is not None:
            params[field] = value

    try:
        raw = await adapter.modify_alert(token, alert_id, params)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to modify alert: {exc}",
        )

    return _to_alert_response(raw, body.provider_id)


@router.delete("")
async def delete_alerts(
    body: AlertDeleteRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, str]:
    """Delete one or more alerts on the specified provider."""
    adapter, token = await _resolve_provider_and_token(
        session, current_user.id, body.provider_id
    )

    if not body.uuids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one uuid is required",
        )

    try:
        await adapter.delete_alerts(token, body.uuids)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to delete alert(s): {exc}",
        )

    return {"status": "success"}
