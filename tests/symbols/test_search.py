import pytest
from terminal.symbols.service import InMemorySymbolProvider


@pytest.fixture
def mock_provider():
    """
    Creates a provider with mock data for testing search logic.
    """
    from unittest.mock import MagicMock

    mock_fs = MagicMock()
    provider = InMemorySymbolProvider(fs=mock_fs, bucket="test-bucket")

    mock_data = [
        {
            "ticker": "NASDAQ:NVDA",
            "name": "nvidia",
            "market": "america",
            "country": "United States",
            "type": "stock",
            "isin": "US67066G1040",
            "indexes": ["S&P 500", "NASDAQ 100"],
            "typespecs": ["common"],
        },
        {
            "ticker": "NSE:RELIANCE",
            "name": "RELIANCE INDUSTRIES",
            "market": "india",
            "country": "India",
            "type": "stock",
            "isin": "INE002A01018",
            "indexes": ["NIFTY 50", "NIFTY 100"],
            "typespecs": ["common"],
        },
        {
            "ticker": "NSE:TCS",
            "name": "TATA CONSULTANCY SERVICES",
            "market": "india",
            "country": "India",
            "type": "stock",
            "isin": "INE467B01029",
            "indexes": ["NIFTY 50", "CNX IT"],
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

    provider._symbols = mock_data
    provider._initialized = True
    provider._build_index()

    return provider


@pytest.mark.asyncio
async def test_search_symbols_query(mock_provider):
    # Search by ticker
    results = await mock_provider.search(query="NVDA", market="america")
    assert len(results) == 1
    assert results[0]["ticker"] == "NASDAQ:NVDA"
    assert "indexes" not in results[0]

    # Search by name
    results = await mock_provider.search(query="RELIANCE", market="india")
    assert len(results) == 1
    assert "RELIANCE" in results[0]["name"]
    assert "indexes" not in results[0]


@pytest.mark.asyncio
async def test_search_symbols_type(mock_provider):
    results = await mock_provider.search(item_type="fund", market="america")
    assert len(results) == 1
    assert results[0]["ticker"] == "NYSE:SPY"

    results = await mock_provider.search(item_type="stock", market="america")
    assert len(results) == 1
    assert results[0]["ticker"] == "NASDAQ:NVDA"


@pytest.mark.asyncio
async def test_search_symbols_market_default(mock_provider):
    # india is default
    results = await mock_provider.search(query="TCS")
    assert len(results) == 1
    assert results[0]["ticker"] == "NSE:TCS"


@pytest.mark.asyncio
async def test_search_symbols_index(mock_provider):
    results = await mock_provider.search(index="NIFTY 50")
    assert len(results) == 2  # RELIANCE and TCS

    results = await mock_provider.search(index="CNX IT")
    assert len(results) == 1
    assert results[0]["ticker"] == "NSE:TCS"


def test_get_search_metadata(mock_provider):
    metadata = mock_provider.get_metadata()
    assert "india" in metadata["markets"]
    assert "america" in metadata["markets"]
    assert "stock" in metadata["types"]
    assert "fund" in metadata["types"]
    assert "NIFTY 50" in metadata["indexes"]
    assert "NASDAQ 100" in metadata["indexes"]
