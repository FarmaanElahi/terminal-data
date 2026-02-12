import json
import os
from typing import List, Dict, Any, Optional
from core.storage import get_fs

# In-memory cache for symbols
_symbols_cache: List[Dict[str, Any]] = None


def _load_symbols() -> List[Dict[str, Any]]:
    """
    Loads symbols from OCI S3 into the in-memory cache.
    """
    global _symbols_cache
    if _symbols_cache is not None:
        return _symbols_cache

    bucket = os.environ.get("OCI_BUCKET")
    if not bucket:
        return []

    fs = get_fs()
    file_path = f"{bucket}/symbols/symbols.json"

    if not fs.exists(file_path):
        return []

    with fs.open(file_path, "r") as f:
        _symbols_cache = json.load(f)

    return _symbols_cache


def search_symbols(
    query: Optional[str] = None,
    country: Optional[str] = "India",
    index: Optional[str] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """
    Searches for symbols in the cached data.
    """
    symbols = _load_symbols()

    results = []
    query = query.lower() if query else None

    for s in symbols:
        # Country filter
        if country and s.get("country") != country:
            continue

        # Index filter (case-insensitive search in the indexes list)
        if index and index not in s.get("indexes", []):
            continue

        # Query filter (matches ticker or name)
        if query:
            match = (
                query in s.get("ticker", "").lower()
                or query in s.get("name", "").lower()
                or query in s.get("isin", "").lower()
            )
            if not match:
                continue

        results.append(s)
        if len(results) >= limit:
            break

    return results


def get_search_metadata() -> Dict[str, List[str]]:
    """
    Returns unique countries and indexes for filtering.
    """
    symbols = _load_symbols()
    countries = set()
    indexes = set()

    for s in symbols:
        countries.add(s.get("country"))
        for idx in s.get("indexes", []):
            indexes.add(idx)

    return {
        "countries": sorted(list(filter(None, countries))),
        "indexes": sorted(list(filter(None, indexes))),
    }


def clear_cache():
    """
    Clears the in-memory symbols cache (useful after a sync).
    """
    global _symbols_cache
    _symbols_cache = None
