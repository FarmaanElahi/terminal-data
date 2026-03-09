"""Abstract base for notification providers."""

from __future__ import annotations

from abc import ABC, abstractmethod


class NotificationProvider(ABC):
    """Interface for alert notification delivery."""

    @abstractmethod
    async def send(
        self,
        channel_config: dict,
        message: str,
        *,
        alert_name: str = "",
        symbol: str = "",
        trigger_value: float | None = None,
    ) -> bool:
        """Send a notification via this provider.

        Parameters
        ----------
        channel_config : dict
            Provider-specific config from ``UserNotificationChannel.config``.
        message : str
            Human-readable alert message.

        Returns
        -------
        bool
            True if sent successfully.
        """
        ...
