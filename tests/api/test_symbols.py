import pytest
from httpx import ASGITransport, AsyncClient
from terminal.main import api
from terminal.symbols.service import InMemorySymbolProvider
from terminal.dependencies import get_symbol_provider


@pytest.fixture
def mock_provider():
    """
    Creates a provider with mock data for testing search API.
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
        },
        {
            "ticker": "NSE:RELIANCE",
            "name": "RELIANCE INDUSTRIES",
            "market": "india",
            "country": "India",
            "type": "stock",
            "isin": "INE002A01018",
            "indexes": ["NIFTY 50", "NIFTY 100"],
        },
    ]
    provider._symbols = mock_data
    provider._initialized = True
    provider._build_index()
    return provider


@pytest.mark.asyncio
async def test_get_symbols_api(mock_provider):
    api.dependency_overrides[get_symbol_provider] = lambda: mock_provider

    transport = ASGITransport(app=api)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Test search
        response = await ac.get("/api/v1/symbols/?q=NVDA&market=america")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["ticker"] == "NASDAQ:NVDA"

    api.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_symbols_metadata_api(mock_provider):
    api.dependency_overrides[get_symbol_provider] = lambda: mock_provider

    transport = ASGITransport(app=api)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/api/v1/symbols/search_metadata")
        assert response.status_code == 200
        data = response.json()
        assert "india" in data["markets"]
        assert "S&P 500" in data["indexes"]

    api.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_sync_symbols_api(monkeypatch, mock_provider):
    """
    Test the sync API endpoint with mock sync logic and DI.
    """
    api.dependency_overrides[get_symbol_provider] = lambda: mock_provider

    # Mock synchronous feature-level sync_symbols (the one from routers/symbols.py)
    import terminal.symbols.router as symbols_api
    from unittest.mock import AsyncMock

    async def mock_sync(**kwargs):
        return 42

    monkeypatch.setattr(symbols_api, "sync_symbols", mock_sync)

    # Mock provider.refresh
    mock_provider.refresh = AsyncMock(return_value=42)

    transport = ASGITransport(app=api)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post("/api/v1/symbols/sync")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "Sync complete"
        assert data["count"] == 42

        # Verify provider refresh was called
        mock_provider.refresh.assert_called_once_with(trigger_sync=False)

    api.dependency_overrides.clear()
