"""
Caching utilities for expression evaluation.
"""

from typing import Any, Dict, Optional


class ExpressionCache:
    """
    Simple in-memory cache for expression evaluation results.

    Provides caching with hit/miss statistics for performance monitoring
    and ability to disable caching entirely.
    """

    def __init__(self, enabled: bool = True):
        """
        Initialize cache with statistics.

        Args:
            enabled: Whether caching is enabled
        """
        self._cache: Dict[str, Any] = {}
        self._hits = 0
        self._misses = 0
        self._enabled = enabled

    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.

        Args:
            key: Cache key

        Returns:
            Optional[Any]: Cached value or None if not found or disabled
        """
        if not self._enabled:
            self._misses += 1
            return None

        if key in self._cache:
            self._hits += 1
            return self._cache[key]
        else:
            self._misses += 1
            return None

    def set(self, key: str, value: Any) -> None:
        """
        Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
        """
        if self._enabled:
            self._cache[key] = value

    def clear(self) -> None:
        """Clear all cache entries and reset statistics."""
        self._cache.clear()
        self._hits = 0
        self._misses = 0

    def enable(self) -> None:
        """Enable caching."""
        self._enabled = True

    def disable(self) -> None:
        """Disable caching and clear existing cache."""
        self._enabled = False
        self._cache.clear()

    def is_enabled(self) -> bool:
        """Check if caching is enabled."""
        return self._enabled

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache performance statistics.

        Returns:
            Dict with cache statistics
        """
        total = self._hits + self._misses
        hit_rate = (self._hits / total * 100) if total > 0 else 0

        return {
            "cache_enabled": self._enabled,
            "cache_hits": self._hits,
            "cache_misses": self._misses,
            "hit_rate_percent": round(hit_rate, 2),
            "cached_expressions": len(self._cache)
        }
