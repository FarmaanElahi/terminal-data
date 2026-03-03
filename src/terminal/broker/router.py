import logging
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from terminal.auth.models import User
from terminal.auth.router import get_current_user
from terminal.broker import service as broker_service
from terminal.broker.models import BrokerStatus
from terminal.candles.feed_registry import feed_registry
from terminal.config import settings
from terminal.dependencies import get_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/broker", tags=["Broker"])


class CallbackRequest(BaseModel):
    code: str


@router.get("/upstox/auth-url")
async def get_upstox_auth_url(
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    """Return the Upstox OAuth2 authorization URL."""
    if not settings.is_upstox_oauth_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Upstox OAuth2 is not configured on this server",
        )
    return {"url": broker_service.build_upstox_auth_url()}


@router.post("/upstox/callback")
async def upstox_callback(
    body: CallbackRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, str]:
    """Exchange an authorization code for an access token and persist it."""
    if not settings.is_upstox_oauth_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Upstox OAuth2 is not configured on this server",
        )

    try:
        access_token = await broker_service.exchange_upstox_code(body.code)
    except Exception as exc:
        logger.error("Upstox token exchange failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to exchange authorization code: {exc}",
        )

    broker_service.save_token(session, current_user.id, "upstox", access_token)
    logger.info("Saved Upstox token for user=%s", current_user.id)

    # If a shared feed is already running for this user (other sessions are open),
    # restart it with the new token. Each session that calls restart_upstox_feed
    # will acquire its own ref if it doesn't have one yet.
    await feed_registry.update_token(current_user.id, access_token)

    # Notify all active WS sessions — they will attach to the (now running) shared feed
    from terminal.realtime.handler import connection_manager

    for ws_session in connection_manager.get_sessions(current_user.id):
        try:
            await ws_session.restart_upstox_feed(access_token)
        except Exception:
            logger.exception(
                "Failed to restart Upstox feed for session user=%s", current_user.id
            )

    return {"status": "success"}


@router.get("/upstox/status", response_model=BrokerStatus)
async def get_upstox_status(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> BrokerStatus:
    """Return the current Upstox connection status for this user."""
    token = broker_service.get_active_token(session, current_user.id, "upstox")
    return BrokerStatus(
        connected=feed_registry.is_connected(current_user.id),
        login_required=not bool(token),
        provider="upstox",
    )
