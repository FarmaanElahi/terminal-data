import pandas as pd
import json
import logging
from fsspec import AbstractFileSystem
from typing import Any
from terminal.tradingview import TradingView
from terminal.config import Settings

logger = logging.getLogger(__name__)

# Global cache for the dataframe
_symbols_df: pd.DataFrame | None = None
symbol_file_path = "symbols.parquet"


async def search(
    fs: AbstractFileSystem,
    settings: Settings,
    text: str | None = None,
    market: str | None = "india",
    item_type: str | None = None,
    index: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """
    Search symbols using Pandas DataFrame.
    """
    df = await _ensure_data_loaded(fs, settings)

    if df.empty:
        return []

    # Apply filters
    filtered_df = df.copy()

    if market:
        filtered_df = filtered_df[filtered_df["market"] == market]

    if item_type:
        filtered_df = filtered_df[filtered_df["type"] == item_type]

    if index:
        # Check if the list of dicts in 'indexes' contains a dict with name == index
        def has_index(indexes_list):
            if not isinstance(indexes_list, list):
                return False
            return any(
                isinstance(idx, dict) and idx.get("name") == index
                for idx in indexes_list
            )

        filtered_df = filtered_df[filtered_df["indexes"].apply(has_index)]

    if text:
        query_lower = text.lower()
        terms = [t for t in query_lower.split() if t]

        # Combine ticker and name for searching, using lower case
        search_series = (
            filtered_df["ticker"].fillna("") + " " + filtered_df["name"].fillna("")
        ).str.lower()

        # For each term in the query, it must be present in the search string
        for term in terms:
            filtered_df = filtered_df[search_series.str.contains(term, regex=False)]
            search_series = search_series[
                filtered_df.index
            ]  # update the series to match filtered_df

    if limit:
        filtered_df = filtered_df.head(limit)

    # Convert to list of dicts matching SymbolSearchResponse
    results = []

    for _, row in filtered_df.iterrows():
        r = row.to_dict()
        # id is required by SymbolSearchResponse, generate it from ticker
        r["id"] = str(r.get("ticker", ""))
        # Ensure isin is None instead of NaN
        if pd.isna(r.get("isin")):
            r["isin"] = None
        results.append(r)

    return results


async def refresh(
    fs: AbstractFileSystem,
    settings: Settings,
    symbols: list[dict[str, Any]] | None = None,
) -> int:
    """
    Syncs a list of symbols to Parquet in OCIFS, or fetches all if none provided.
    """
    global _symbols_df

    if symbols is None:
        symbols = await get_all_symbols_external()

    if not symbols:
        return 0

    # Ensure arrays are serialized to JSON strings for Parquet to avoid nested array schema issues
    df = pd.DataFrame(symbols)

    for col in ["indexes", "typespecs"]:
        if col in df.columns:
            df[col] = df[col].apply(lambda x: json.dumps(x))

    # Save to OCIFS
    file_path = settings.abs_file_path(symbol_file_path)
    with fs.open(file_path, "wb") as f:
        # Pandas can write parquet buffer, ocifs handles it
        df.to_parquet(f, index=False)

    # Reset cache
    _symbols_df = None

    return len(symbols)


async def _ensure_data_loaded(fs: Any, settings: Settings) -> pd.DataFrame:
    global _symbols_df
    if _symbols_df is not None:
        return _symbols_df

    file_path = settings.abs_file_path(symbol_file_path)

    # Check if file exists
    if not fs.exists(file_path):
        logger.info(
            f"Symbols Parquet not found at {file_path}. Fetching from external source."
        )
        await refresh(fs, settings)

    # Load from Parquet using pandas via OCIFS
    logger.info(f"Loading symbols from {file_path}")
    with fs.open(file_path, "rb") as f:
        _symbols_df = pd.read_parquet(f)

    # Process JSON fields if they are strings.
    if not _symbols_df.empty:
        for col in ["indexes", "typespecs"]:
            if col in _symbols_df.columns:
                _symbols_df[col] = _symbols_df[col].apply(
                    lambda x: (
                        json.loads(x)
                        if isinstance(x, str)
                        else (x if pd.notna(x) else [])
                    )
                )

    return _symbols_df


async def get_filter_metadata(fs: Any, settings: Settings) -> dict[str, list[str]]:
    """
    Returns available filter options (markets, indexes, types).
    """
    df = await _ensure_data_loaded(fs, settings)

    if df.empty:
        return {"markets": [], "types": [], "indexes": []}

    markets = [m for m in df["market"].dropna().unique().tolist() if m]
    types = [t for t in df["type"].dropna().unique().tolist() if t]

    unique_indexes = set()
    for idxs in df["indexes"].dropna():
        if isinstance(idxs, list):
            for idx in idxs:
                if isinstance(idx, dict) and "name" in idx:
                    unique_indexes.add(idx["name"])
                elif isinstance(idx, str):
                    unique_indexes.add(idx)

    return {
        "markets": sorted(list(markets)),
        "types": sorted(list(types)),
        "indexes": sorted(list(unique_indexes)),
    }


async def all_ticker(fs: AbstractFileSystem, settings: Settings) -> list[str]:
    """
    Returns a list of all symbol tickers.
    """
    df = await _ensure_data_loaded(fs, settings)
    if df.empty:
        return []
    return df["ticker"].dropna().unique().tolist()


async def get_all_symbols_external() -> list[dict[str, Any]]:
    """
    Syncs symbols from TradingView.
    """
    return await TradingView().scanner.fetch_symbols()
