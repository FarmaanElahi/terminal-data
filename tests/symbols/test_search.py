import pytest
import pytest_asyncio
from sqlmodel import Session
from terminal.symbols import service as symbol_service


@pytest_asyncio.fixture
async def seeded_session(session: Session):
    """
    Creates a session with mock data for testing search logic.
    """
    mock_data = [
        {
            "ticker": "NASDAQ:NVDA",
            "name": "nvidia",
            "market": "america",
            "country": "United States",
            "type": "stock",
            "isin": "US67066G1040",
            "indexes": [
                {"name": "S&P 500", "proname": "SPX"},
                {"name": "NASDAQ 100", "proname": "NDX"},
            ],
            "typespecs": ["common"],
        },
        {
            "ticker": "NSE:RELIANCE",
            "name": "RELIANCE INDUSTRIES",
            "market": "india",
            "country": "India",
            "type": "stock",
            "isin": "INE002A01018",
            "indexes": [
                {"name": "NIFTY 50", "proname": "NSE:NIFTY"},
                {"name": "NIFTY 100", "proname": "NSE:NIFTY100"},
            ],
            "typespecs": ["common"],
        },
        {
            "ticker": "NSE:TCS",
            "name": "TATA CONSULTANCY SERVICES",
            "market": "india",
            "country": "India",
            "type": "stock",
            "isin": "INE467B01029",
            "indexes": [
                {"name": "NIFTY 50", "proname": "NSE:NIFTY"},
                {"name": "CNX IT", "proname": "NSE:CNXIT"},
            ],
            "typespecs": ["common"],
        },
        {
            "ticker": "NYSE:SPY",
            "name": "SPDR S&P 500 ETF TRUST",
            "market": "america",
            "country": "United States",
            "type": "fund",
            "isin": "US78462F1030",
            "indexes": [],
            "typespecs": ["etf"],
        },
    ]

    await symbol_service.refresh(session, mock_data)
    return session


@pytest.mark.asyncio
async def test_search_symbols_query(seeded_session):
    # Search by ticker
    results = await symbol_service.search(
        seeded_session, query="NVDA", market="america"
    )
    assert len(results) == 1
    assert results[0].ticker == "NASDAQ:NVDA"

    # Search by name
    results = await symbol_service.search(
        seeded_session, query="RELIANCE", market="india"
    )
    assert len(results) == 1
    assert "RELIANCE" in results[0].name


@pytest.mark.asyncio
async def test_search_symbols_type(seeded_session):
    results = await symbol_service.search(
        seeded_session, item_type="fund", market="america"
    )
    assert len(results) == 1
    assert results[0].ticker == "NYSE:SPY"

    results = await symbol_service.search(
        seeded_session, item_type="stock", market="america"
    )
    assert len(results) == 1
    assert results[0].ticker == "NASDAQ:NVDA"


@pytest.mark.asyncio
async def test_search_symbols_market_default(seeded_session):
    results = await symbol_service.search(seeded_session, query="TCS")
    assert len(results) == 1
    assert results[0].ticker == "NSE:TCS"


@pytest.mark.asyncio
async def test_search_symbols_index(seeded_session):
    results = await symbol_service.search(
        seeded_session, index="NIFTY 50", market="india"
    )
    assert len(results) == 2  # RELIANCE and TCS

    results = await symbol_service.search(
        seeded_session, index="CNX IT", market="india"
    )
    assert len(results) == 1
    assert results[0].ticker == "NSE:TCS"


def test_get_search_metadata(seeded_session):
    metadata = symbol_service.get_metadata(seeded_session)
    assert "india" in metadata["markets"]
    assert "america" in metadata["markets"]
    assert "stock" in metadata["types"]
    assert "fund" in metadata["types"]
    assert "NIFTY 50" in metadata["indexes"]
    assert "NASDAQ 100" in metadata["indexes"]
