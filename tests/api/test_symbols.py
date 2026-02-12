import pytest
from httpx import ASGITransport, AsyncClient
from main import app
import features.symbols.search as symbols_search


@pytest.fixture
def mock_symbols_data(monkeypatch):
    """
    Mocks the symbols data for testing search API.
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
    ]
    monkeypatch.setattr(symbols_search, "_symbols_cache", mock_data)
    return mock_data


@pytest.mark.asyncio
async def test_get_symbols_api(mock_symbols_data):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Test search
        response = await ac.get("/api/symbols/?q=NVDA&country=United States")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["ticker"] == "NASDAQ:NVDA"


@pytest.mark.asyncio
async def test_get_symbols_metadata_api(mock_symbols_data):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/api/symbols/search_metadata")
        assert response.status_code == 200
        data = response.json()
        assert "India" in data["countries"]
        assert "S&P 500" in data["indexes"]
