"""Web Push notification provider — uses VAPID-based browser push."""

from __future__ import annotations

import json
import logging

from terminal.notifications.base import NotificationProvider

logger = logging.getLogger(__name__)


class WebPushProvider(NotificationProvider):
    """Sends push notifications via the Web Push protocol (VAPID).

    Requires:
      - ``VAPID_PRIVATE_KEY`` and ``VAPID_CLAIMS_EMAIL`` in app config
      - User's push subscription JSON in ``channel_config["subscription"]``

    Uses the ``pywebpush`` library.
    """

    def __init__(
        self,
        vapid_private_key: str,
        vapid_claims_email: str,
    ) -> None:
        self.vapid_private_key = vapid_private_key
        self.vapid_claims_email = vapid_claims_email

    async def send(
        self,
        channel_config: dict,
        message: str,
        *,
        alert_name: str = "",
        symbol: str = "",
        trigger_value: float | None = None,
    ) -> bool:
        subscription = channel_config.get("subscription")
        if not subscription:
            logger.warning("Web Push channel missing subscription")
            return False

        if not self.vapid_private_key:
            logger.warning("VAPID private key not configured")
            return False

        payload = json.dumps({
            "title": f"🔔 {alert_name}" if alert_name else "🔔 Alert Triggered",
            "body": message,
            "icon": "/favicon.ico",
            "data": {
                "symbol": symbol,
                "trigger_value": trigger_value,
            },
        })

        try:
            # Import lazily to avoid hard dependency
            from pywebpush import webpush, WebPushException

            webpush(
                subscription_info=subscription,
                data=payload,
                vapid_private_key=self.vapid_private_key,
                vapid_claims={"sub": f"mailto:{self.vapid_claims_email}"},
            )
            logger.debug("Web Push notification sent")
            return True
        except Exception as e:
            logger.error("Web Push send failed: %s", e)
            return False
