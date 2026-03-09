"""Notification dispatcher — routes alerts to configured providers."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from sqlalchemy.orm import Session

from terminal.alerts import service as alerts_service
from terminal.database.core import engine as db_engine
from terminal.notifications.base import NotificationProvider
from terminal.notifications.in_app import InAppProvider
from terminal.notifications.telegram import TelegramProvider
from terminal.notifications.web_push import WebPushProvider

logger = logging.getLogger(__name__)


class NotificationDispatcher:
    """Routes alert notifications to the appropriate provider(s).

    Initialized with config from ``Settings`` and provides a
    ``dispatch()`` method called by the alert engine.
    """

    def __init__(
        self,
        *,
        telegram_bot_token: str = "",
        vapid_private_key: str = "",
        vapid_claims_email: str = "",
    ) -> None:
        self._providers: dict[str, NotificationProvider] = {
            "in_app": InAppProvider(),
        }

        if telegram_bot_token:
            self._providers["telegram"] = TelegramProvider(telegram_bot_token)
            logger.info("Telegram notification provider enabled")

        if vapid_private_key and vapid_claims_email:
            self._providers["web_push"] = WebPushProvider(
                vapid_private_key, vapid_claims_email
            )
            logger.info("Web Push notification provider enabled")

    async def dispatch(
        self,
        user_id: str,
        channel_ids: list[str],
        message: str,
        *,
        alert_name: str = "",
        symbol: str = "",
        trigger_value: float | None = None,
    ) -> dict[str, bool]:
        """Send notification to all specified channels.

        Returns a dict mapping channel_id → success boolean.
        """
        if not channel_ids:
            return {}

        # Fetch channel configs from DB
        with Session(db_engine) as session:
            channels = alerts_service.get_channels_by_ids(session, channel_ids)

        results: dict[str, bool] = {}
        tasks = []

        for channel in channels:
            provider = self._providers.get(channel.channel_type)
            if provider is None:
                logger.warning(
                    "No provider for channel type '%s'", channel.channel_type
                )
                results[channel.id] = False
                continue

            tasks.append(
                self._send_one(
                    provider,
                    channel.id,
                    channel.config,
                    message,
                    alert_name=alert_name,
                    symbol=symbol,
                    trigger_value=trigger_value,
                    results=results,
                )
            )

        if tasks:
            await asyncio.gather(*tasks)

        return results

    @staticmethod
    async def _send_one(
        provider: NotificationProvider,
        channel_id: str,
        channel_config: dict,
        message: str,
        *,
        alert_name: str,
        symbol: str,
        trigger_value: float | None,
        results: dict[str, bool],
    ) -> None:
        """Send a single notification and record result."""
        try:
            success = await provider.send(
                channel_config,
                message,
                alert_name=alert_name,
                symbol=symbol,
                trigger_value=trigger_value,
            )
            results[channel_id] = success
        except Exception as e:
            logger.error("Notification send failed for channel %s: %s", channel_id, e)
            results[channel_id] = False

    async def close(self) -> None:
        """Cleanup provider resources."""
        for provider in self._providers.values():
            if hasattr(provider, "close"):
                await provider.close()
