"""In-app notification provider — pushes via WebSocket for toast display."""

from __future__ import annotations

import logging

from terminal.notifications.base import NotificationProvider

logger = logging.getLogger(__name__)


class InAppProvider(NotificationProvider):
    """In-app notification delivered via WebSocket.

    The actual WebSocket push is handled by ``AlertEngine._push_to_sessions()``,
    so this provider is a no-op for external send. It exists for consistency
    in the provider registry and for potential future extensions (e.g. storing
    in-app notification state).
    """

    async def send(
        self,
        channel_config: dict,
        message: str,
        *,
        alert_name: str = "",
        symbol: str = "",
        trigger_value: float | None = None,
    ) -> bool:
        # In-app notifications are pushed directly via WebSocket in the engine.
        # This provider is registered but doesn't need to do external HTTP calls.
        logger.debug("In-app notification: %s", message)
        return True
