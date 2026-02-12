from abc import ABC, abstractmethod
from typing import Any
import json


class SymbolProvider(ABC):
    """
    Abstract base class for symbol data access.
    """

    @abstractmethod
    async def search(
        self,
        query: str | None = None,
        market: str | None = "india",
        item_type: str | None = None,
        index: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        pass

    @abstractmethod
    def get_metadata(self) -> dict[str, list[str]]:
        pass

    @abstractmethod
    async def refresh(self, trigger_sync: bool = False) -> int:
        """Reloads data from storage, optionally triggering a sync."""
        pass


class InMemorySymbolProvider(SymbolProvider):
    """
    High-performance in-memory symbol provider with indexing.
    """

    def __init__(self, fs: Any, bucket: str):
        self.fs = fs
        self.bucket = bucket
        self._symbols: list[dict[str, Any]] = []
        self._by_market: dict[str, list[int]] = {}  # index in self._symbols
        self._by_type: dict[str, list[int]] = {}
        self._markets: set[str] = set()
        self._types: set[str] = set()
        self._indexes: set[str] = set()
        self._initialized = False

    async def _ensure_loaded(self):
        if not self._initialized:
            await self.refresh(trigger_sync=False)

    def _build_index(self):
        """Builds market and type indexes for O(1) initial access."""
        self._by_market = {}
        self._by_type = {}
        self._markets = set()
        self._types = set()
        self._indexes = set()

        for idx, s in enumerate(self._symbols):
            m = s.get("market")
            t = s.get("type")
            idxs = s.get("indexes", [])

            if m:
                self._markets.add(m)
                self._by_market.setdefault(m, []).append(idx)

            if t:
                self._types.add(t)
                self._by_type.setdefault(t, []).append(idx)

            for i in idxs:
                self._indexes.add(i)

    @staticmethod
    async def persist_symbols(
        fs: Any, bucket: str, symbols: list[dict[str, Any]]
    ) -> int:
        """
        Persists provided symbols to OCI S3 storage.
        """
        if not bucket:
            raise ValueError("OCI_BUCKET environment variable is not set")

        file_path = f"{bucket}/symbols/symbols.json"

        with fs.open(file_path, "w") as f:
            json.dump(symbols, f)

        return len(symbols)

    async def refresh(self, trigger_sync: bool = False) -> int:
        file_path = f"{self.bucket}/symbols/symbols.json"

        if not self.fs.exists(file_path):
            self._initialized = True
            return 0

        with self.fs.open(file_path, "r") as f:
            self._symbols = json.load(f)

        self._build_index()
        self._initialized = True
        return len(self._symbols)

    async def search(
        self,
        query: str | None = None,
        market: str | None = "india",
        item_type: str | None = None,
        index: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        await self._ensure_loaded()

        # 1. Start with the most restrictive indexed set
        candidates: list[int] = []

        if market and market in self._by_market:
            candidates = self._by_market[market]
        elif market:
            return []  # Market requested but not found
        else:
            candidates = list(range(len(self._symbols)))

        results = []
        query = query.lower() if query else None

        for idx in candidates:
            s = self._symbols[idx]

            # 2. Sequential filters
            if item_type and s.get("type") != item_type:
                continue

            if index and index not in s.get("indexes", []):
                continue

            if query:
                match = (
                    query in s.get("ticker", "").lower()
                    or query in s.get("name", "").lower()
                    or query in s.get("isin", "").lower()
                )
                if not match:
                    continue

            # Return a copy without 'indexes'
            res = s.copy()
            res.pop("indexes", None)
            results.append(res)
            if len(results) >= limit:
                break

        return results

    def get_metadata(self) -> dict[str, list[str]]:
        return {
            "markets": sorted(list(self._markets)),
            "indexes": sorted(list(self._indexes)),
            "types": sorted(list(self._types)),
        }
