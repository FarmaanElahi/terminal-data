import pytest
from sqlalchemy.orm import Session
from sqlalchemy import select
from terminal.symbols.models import Symbol
from terminal.symbols import service as symbol_service


@pytest.mark.asyncio
async def test_symbol_fts_search(session: Session):
    # 1. Seed some symbols
    symbols = [
        {
            "ticker": "AAPL",
            "name": "Apple Inc.",
            "type": "stock",
            "market": "america",
            "indexes": [{"name": "NASDAQ 100", "proname": "NASDAQ:NDX"}],
            "typespecs": ["common"],
        },
        {
            "ticker": "MSFT",
            "name": "Microsoft Corporation",
            "type": "stock",
            "market": "america",
            "indexes": [{"name": "NASDAQ 100", "proname": "NASDAQ:NDX"}],
            "typespecs": ["common"],
        },
        {
            "ticker": "RELIANCE",
            "name": "Reliance Industries",
            "type": "stock",
            "market": "india",
            "indexes": [{"name": "NIFTY 50", "proname": "NSE:NIFTY"}],
            "typespecs": ["common"],
        },
        {
            "ticker": "TCS",
            "name": "Tata Consultancy Services",
            "type": "stock",
            "market": "india",
            "indexes": [{"name": "NIFTY 50", "proname": "NSE:NIFTY"}],
            "typespecs": ["common"],
        },
    ]
    await symbol_service.refresh(session, symbols)

    # 2. Search by ticker (prefix)
    results = await symbol_service.search(session, query="AA", market="america")
    assert len(results) == 1
    assert results[0].ticker == "AAPL"

    # 3. Search by name
    results = await symbol_service.search(session, query="Microsoft", market="america")
    assert len(results) == 1
    assert results[0].ticker == "MSFT"

    # 4. Search by partial name prefix
    results = await symbol_service.search(session, query="Relia", market="india")
    assert len(results) == 1
    assert results[0].ticker == "RELIANCE"

    # 5. Search with multiple terms
    results = await symbol_service.search(session, query="Tata Consu", market="india")
    assert len(results) == 1
    assert results[0].ticker == "TCS"

    # 6. Filter by index
    results = await symbol_service.search(session, index="NIFTY 50", market="india")
    assert len(results) == 2
    tickers = {r.ticker for r in results}
    assert "RELIANCE" in tickers
    assert "TCS" in tickers


@pytest.mark.asyncio
async def test_get_metadata(session: Session):
    symbols = [
        {
            "ticker": "AAPL",
            "name": "Apple Inc.",
            "type": "stock",
            "market": "america",
            "indexes": [{"name": "NASDAQ 100", "proname": "NASDAQ:NDX"}],
            "typespecs": ["common"],
        },
        {
            "ticker": "RELIANCE",
            "name": "Reliance Industries",
            "type": "stock",
            "market": "india",
            "indexes": [{"name": "NIFTY 50", "proname": "NSE:NIFTY"}],
            "typespecs": ["common"],
        },
    ]
    await symbol_service.refresh(session, symbols)

    metadata = symbol_service.get_metadata(session)
    assert "america" in metadata["markets"]
    assert "india" in metadata["markets"]
    assert "NASDAQ 100" in metadata["indexes"]
    assert "NIFTY 50" in metadata["indexes"]
    assert "stock" in metadata["types"]


@pytest.mark.asyncio
async def test_symbol_upsert_logic(session: Session):
    # 1. Initial sync
    initial_symbols = [
        {
            "ticker": "AAPL",
            "name": "Apple",
            "type": "stock",
            "market": "america",
        }
    ]
    await symbol_service.refresh(session, initial_symbols)

    symbol = (
        session.execute(select(Symbol).where(Symbol.ticker == "AAPL")).scalars().first()
    )
    assert symbol.name == "Apple"

    # 2. Sync with updated name for same ticker
    updated_symbols = [
        {
            "ticker": "AAPL",
            "name": "Apple Inc.",
            "type": "stock",
            "market": "america",
        }
    ]
    await symbol_service.refresh(session, updated_symbols)

    # 3. Verify total count and updated data
    all_symbols = list(session.execute(select(Symbol)).scalars().all())
    assert len(all_symbols) == 1
    assert all_symbols[0].ticker == "AAPL"
    assert all_symbols[0].name == "Apple Inc."
