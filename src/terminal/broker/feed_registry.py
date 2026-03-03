"""Per-user broker feed pool keyed by ``(user_id, provider_id)``."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from terminal.broker.registry import broker_registry

logger = logging.getLogger(__name__)


class BrokerFeedRegistry:
    def __init__(self) -> None:
        self._feeds: dict[tuple[str, str], Any] = {}
        self._ref_counts: dict[tuple[str, str], int] = {}
        self._lock = asyncio.Lock()

    async def acquire(self, user_id: str, provider_id: str, token: str) -> Any | None:
        """Return shared feed for a user+provider, starting it if needed."""
        adapter = broker_registry.get(provider_id)
        if adapter is None:
            return None

        key = (user_id, provider_id)
        feed_to_start = None

        async with self._lock:
            if key not in self._feeds:
                feed = adapter.create_feed(token)
                if feed is None:
                    return None
                self._feeds[key] = feed
                self._ref_counts[key] = 0
                feed_to_start = feed

            self._ref_counts[key] = self._ref_counts.get(key, 0) + 1
            feed = self._feeds[key]

        if feed_to_start is not None:
            await feed_to_start.start()
            logger.info("Started %s feed for user=%s", provider_id, user_id)

        return feed

    async def release(self, user_id: str, provider_id: str) -> None:
        """Decrement ref count and stop feed when no sessions remain."""
        key = (user_id, provider_id)
        feed_to_stop = None

        async with self._lock:
            count = self._ref_counts.get(key, 0) - 1
            if count <= 0:
                feed_to_stop = self._feeds.pop(key, None)
                self._ref_counts.pop(key, None)
            else:
                self._ref_counts[key] = count

        if feed_to_stop is not None:
            await feed_to_stop.stop()
            logger.info(
                "Stopped %s feed for user=%s (no more sessions)",
                provider_id,
                user_id,
            )

    async def update_token(self, user_id: str, provider_id: str, new_token: str) -> None:
        """Update token for active feed if it exists."""
        key = (user_id, provider_id)

        async with self._lock:
            feed = self._feeds.get(key)

        if feed is None:
            return

        update_token = getattr(feed, "update_token", None)
        if callable(update_token):
            await update_token(new_token)
            logger.info("Updated %s token for user=%s", provider_id, user_id)

    async def drop(self, user_id: str, provider_id: str) -> None:
        """Force-stop and remove a feed regardless of current ref count."""
        key = (user_id, provider_id)
        feed_to_stop = None

        async with self._lock:
            feed_to_stop = self._feeds.pop(key, None)
            self._ref_counts.pop(key, None)

        if feed_to_stop is not None:
            await feed_to_stop.stop()
            logger.info("Dropped %s feed for user=%s", provider_id, user_id)

    def get_feed(self, user_id: str, provider_id: str) -> Any | None:
        return self._feeds.get((user_id, provider_id))

    def is_connected(self, user_id: str, provider_id: str) -> bool:
        feed = self._feeds.get((user_id, provider_id))
        if feed is None:
            return False
        return bool(getattr(feed, "is_connected", False))


feed_registry = BrokerFeedRegistry()
