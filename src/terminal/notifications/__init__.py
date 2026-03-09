"""Notification providers — pluggable alert delivery channels."""

from terminal.notifications.base import NotificationProvider
from terminal.notifications.dispatcher import NotificationDispatcher

__all__ = [
    "NotificationProvider",
    "NotificationDispatcher",
]
