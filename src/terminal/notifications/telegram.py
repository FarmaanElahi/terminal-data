"""Telegram notification provider — sends via Telegram Bot API."""

from __future__ import annotations

import logging

import httpx

from terminal.notifications.base import NotificationProvider

logger = logging.getLogger(__name__)

# Telegram Bot API base URL
_TELEGRAM_API = "https://api.telegram.org"


class TelegramProvider(NotificationProvider):
    """Sends alert notifications via Telegram Bot API.

    Requires:
      - ``TELEGRAM_BOT_TOKEN`` in app config
      - User's ``chat_id`` in ``channel_config["chat_id"]``
    """

    def __init__(self, bot_token: str) -> None:
        self.bot_token = bot_token
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=10.0)
        return self._client

    async def send(
        self,
        channel_config: dict,
        message: str,
        *,
        alert_name: str = "",
        symbol: str = "",
        trigger_value: float | None = None,
    ) -> bool:
        chat_id = channel_config.get("chat_id")
        if not chat_id:
            logger.warning("Telegram channel missing chat_id")
            return False

        if not self.bot_token:
            logger.warning("Telegram bot token not configured")
            return False

        # Format message with emoji
        formatted = self._format_message(message, alert_name, symbol, trigger_value)

        try:
            client = await self._get_client()
            resp = await client.post(
                f"{_TELEGRAM_API}/bot{self.bot_token}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": formatted,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                },
            )
            resp.raise_for_status()
            logger.debug("Telegram notification sent to chat_id=%s", chat_id)
            return True
        except httpx.HTTPStatusError as e:
            logger.error(
                "Telegram API error (status=%d): %s",
                e.response.status_code,
                e.response.text,
            )
            return False
        except Exception as e:
            logger.error("Telegram send failed: %s", e)
            return False

    @staticmethod
    def _format_message(
        message: str,
        alert_name: str,
        symbol: str,
        trigger_value: float | None,
    ) -> str:
        """Format alert as a rich Telegram message."""
        parts = ["🔔 <b>Alert Triggered</b>"]
        if alert_name:
            parts.append(f"📋 <b>{alert_name}</b>")
        if symbol:
            parts.append(f"📈 Symbol: <code>{symbol}</code>")
        if trigger_value is not None:
            parts.append(f"💰 Value: <code>{trigger_value:.2f}</code>")
        parts.append(f"\n{message}")
        return "\n".join(parts)

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
