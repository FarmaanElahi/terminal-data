"""Per-user Upstox feed pool.

One ``UpstoxFeed`` per user, shared across all their ``RealtimeSession``s.
Ref-counted: the feed starts on the first ``acquire`` and stops when the
last ``release`` brings the count back to zero.
"""

import asyncio
import logging

from .feed import UpstoxFeed

logger = logging.getLogger(__name__)


class UpstoxFeedRegistry:
    def __init__(self) -> None:
        self._feeds: dict[str, UpstoxFeed] = {}    # user_id → feed
        self._ref_counts: dict[str, int] = {}       # user_id → active session count
        self._lock = asyncio.Lock()

    async def acquire(self, user_id: str, token: str) -> UpstoxFeed:
        """Return the shared feed for this user, starting it if needed.

        Increments the ref count. Call ``release`` when the session ends.
        """
        async with self._lock:
            if user_id not in self._feeds:
                feed = UpstoxFeed(access_token=token)
                await feed.start()
                self._feeds[user_id] = feed
                self._ref_counts[user_id] = 0
                logger.info("Started Upstox feed for user=%s", user_id)
            self._ref_counts[user_id] += 1
            return self._feeds[user_id]

    async def release(self, user_id: str) -> None:
        """Decrement ref count. Stops and removes the feed when it reaches zero."""
        async with self._lock:
            count = self._ref_counts.get(user_id, 0) - 1
            if count <= 0:
                feed = self._feeds.pop(user_id, None)
                self._ref_counts.pop(user_id, None)
                if feed:
                    await feed.stop()
                    logger.info("Stopped Upstox feed for user=%s (no more sessions)", user_id)
            else:
                self._ref_counts[user_id] = count

    async def update_token(self, user_id: str, new_token: str) -> None:
        """Restart the user's feed with a new token.

        No-op if no feed exists for this user (sessions will acquire on
        ``restart_upstox_feed``).
        """
        async with self._lock:
            feed = self._feeds.get(user_id)
        if feed:
            await feed.update_token(new_token)
            logger.info("Updated Upstox token for user=%s", user_id)

    def get_feed(self, user_id: str) -> UpstoxFeed | None:
        """Return the current feed without modifying ref counts."""
        return self._feeds.get(user_id)

    def is_connected(self, user_id: str) -> bool:
        feed = self._feeds.get(user_id)
        return feed is not None and feed.is_connected


# Module-level singleton used by handler.py, broker/router.py, and session.py
feed_registry = UpstoxFeedRegistry()
