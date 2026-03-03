"""Backward-compatible re-export of broker feed registry."""

from terminal.broker.feed_registry import BrokerFeedRegistry, feed_registry

__all__ = ["BrokerFeedRegistry", "feed_registry"]
