"""REST API for managing notification channels."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from terminal.alerts import service as alerts_service
from terminal.alerts.models import (
    NotificationChannelCreate,
    NotificationChannelPublic,
)
from terminal.auth.models import User
from terminal.auth.router import get_current_user
from terminal.dependencies import get_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("/channels", response_model=list[NotificationChannelPublic])
async def list_channels(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[NotificationChannelPublic]:
    """List all notification channels for the current user."""
    channels = await alerts_service.list_channels(session, current_user.id)
    return [NotificationChannelPublic.model_validate(c) for c in channels]


@router.post(
    "/channels",
    response_model=NotificationChannelPublic,
    status_code=status.HTTP_201_CREATED,
)
async def create_channel(
    body: NotificationChannelCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> NotificationChannelPublic:
    """Create a notification channel (Telegram, Web Push, etc.)."""
    channel = await alerts_service.create_channel(session, current_user.id, body)
    return NotificationChannelPublic.model_validate(channel)


@router.delete("/channels/{channel_id}")
async def delete_channel(
    channel_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    """Delete a notification channel."""
    channel = await alerts_service.get_channel(session, channel_id, current_user.id)
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Channel not found",
        )
    await alerts_service.delete_channel(session, channel)
    return {"status": "deleted"}


@router.get("/vapid-key")
async def get_vapid_key() -> dict[str, str]:
    """Get the VAPID public key for Web Push subscription."""
    from terminal.config import settings

    key = getattr(settings, "vapid_public_key", "")
    if not key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Web Push not configured",
        )
    return {"public_key": key}
