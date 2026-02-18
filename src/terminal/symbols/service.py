from typing import Any
from sqlmodel import Session, select, func
from terminal.symbols.models import Symbol
from sqlalchemy.dialects.postgresql import insert as pg_insert


async def search(
    session: Session,
    query: str | None = None,
    market: str | None = "india",
    item_type: str | None = None,
    index: str | None = None,
    limit: int = 100,
) -> list[Symbol]:
    """
    Search symbols using PostgreSQL Full-Text Search or basic filters.
    """
    statement = select(Symbol)

    if market:
        statement = statement.where(Symbol.market == market)

    if item_type:
        statement = statement.where(Symbol.type == item_type)

    if index:
        # PostgreSQL JSONB containment check (@>)
        # We search for an object with matching name within the indexes array
        statement = statement.where(Symbol.indexes.contains([{"name": index}]))

    if query:
        # Clean query and prepare for prefix matching
        # e.g. "aa pl" -> "aa:* & pl:*"
        clean_query = " & ".join([f"{term}:*" for term in query.split() if term])
        if clean_query:
            ts_query = func.to_tsquery("english", clean_query)
            statement = statement.where(Symbol.search_vector.op("@@")(ts_query))
            # Sort by rank descending
            statement = statement.order_by(
                func.ts_rank(Symbol.search_vector, ts_query).desc()
            )

    statement = statement.limit(limit)
    return list(session.exec(statement).all())


async def refresh(session: Session, symbols: list[dict[str, Any]]) -> int:
    """
    Syncs a list of symbols into the database using an efficient upsert strategy.
    Existing symbols (matched by ticker) are updated, others are inserted.
    """
    if not symbols:
        return 0

    # Prepare symbol data (strip non-model fields if any)
    data_list = [
        {
            "ticker": s.get("ticker"),
            "name": s.get("name"),
            "type": s.get("type"),
            "market": s.get("market"),
            "isin": s.get("isin"),
            "indexes": s.get("indexes", []),
            "typespecs": s.get("typespecs", []),
        }
        for s in symbols
    ]

    # Optimized idiomatic bulk upsert for PostgreSQL using Session.execute(stmt, params)
    # This is the native SQLAlchemy 2.0 pattern for batch execution
    stmt = pg_insert(Symbol)
    stmt = stmt.on_conflict_do_update(
        index_elements=["ticker"],
        set_={
            "name": stmt.excluded.name,
            "type": stmt.excluded.type,
            "market": stmt.excluded.market,
            "isin": stmt.excluded.isin,
            "indexes": stmt.excluded.indexes,
            "typespecs": stmt.excluded.typespecs,
        },
    )
    session.execute(stmt, data_list)
    session.commit()
    return len(symbols)


def get_metadata(session: Session) -> dict[str, list[str]]:
    """
    Returns available filter options (markets, indexes, types).
    """
    markets = session.exec(select(Symbol.market).distinct()).all()
    types = session.exec(select(Symbol.type).distinct()).all()

    # Indexes are in a JSON column, so we might need a different approach for distinct values
    all_symbols = session.exec(select(Symbol.indexes)).all()
    unique_indexes = set()
    for idxs in all_symbols:
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
