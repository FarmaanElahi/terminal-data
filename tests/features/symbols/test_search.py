import pytest
from features.symbols import search_symbols, get_search_metadata
from features.symbols.search import _symbols_cache
import features.symbols.search as symbols_search


@pytest.fixture(autouse=True)
def mock_symbols_data(monkeypatch):
    """
    Mocks the symbols data for testing search logic.
    """
    mock_data = [
        {
            "ticker": "NASDAQ:NVDA",
            "name": "nvidia",
            "country": "United States",
            "isin": "US67066G1040",
            "indexes": ["S&P 500", "NASDAQ 100"],
        },
        {
            "ticker": "NSE:RELIANCE",
            "name": "RELIANCE INDUSTRIES",
            "country": "India",
            "isin": "INE002A01018",
            "indexes": ["NIFTY 50", "NIFTY 100"],
        },
        {
            "ticker": "NSE:TCS",
            "name": "TATA CONSULTANCY SERVICES",
            "country": "India",
            "isin": "INE467B01029",
            "indexes": ["NIFTY 50", "CNX IT"],
        },
    ]
    monkeypatch.setattr(symbols_search, "_symbols_cache", mock_data)
    yield mock_data
    monkeypatch.setattr(symbols_search, "_symbols_cache", None)


def test_search_symbols_query():
    # Search by ticker
    results = search_symbols(query="NVDA", country="United States")
    assert len(results) == 1
    assert results[0]["ticker"] == "NASDAQ:NVDA"

    # Search by name
    results = search_symbols(query="RELIANCE", country="India")
    assert len(results) == 1
    assert "RELIANCE" in results[0]["name"]


def test_search_symbols_country_default():
    # India is default
    results = search_symbols(query="TCS")
    assert len(results) == 1
    assert results[0]["ticker"] == "NSE:TCS"


def test_search_symbols_index():
    results = search_symbols(index="NIFTY 50")
    assert len(results) == 2  # RELIANCE and TCS

    results = search_symbols(index="CNX IT")
    assert len(results) == 1
    assert results[0]["ticker"] == "NSE:TCS"


def test_get_search_metadata():
    metadata = get_search_metadata()
    assert "India" in metadata["countries"]
    assert "United States" in metadata["countries"]
    assert "NIFTY 50" in metadata["indexes"]
    assert "NASDAQ 100" in metadata["indexes"]
