import pytest
from httpx import ASGITransport, AsyncClient
from main import app
from unittest.mock import patch, AsyncMock
from fsspec.implementations.memory import MemoryFileSystem
from internal.features.symbols.provider import InMemorySymbolProvider
from api.deps import get_symbol_provider, get_fs, get_settings
from api.config import Settings


@pytest.mark.asyncio
async def test_full_sync_and_search_flow():
    """
    Tests the full flow from fetching (mocked) to search via API with DI.
    """
    mock_symbols = [
        {
            "ticker": "NSE:RELIANCE",
            "name": "RELIANCE INDUSTRIES",
            "country": "India",
            "market": "india",
            "type": "stock",
            "isin": "INE002A01018",
            "indexes": ["NIFTY 50"],
        }
    ]

    # Use MemoryFileSystem for storage testing
    mfs = MemoryFileSystem()
    bucket = "test-bucket"

    # Setup a fresh provider for DI with constructor injection
    test_provider = InMemorySymbolProvider(fs=mfs, bucket=bucket)

    # Dependency overrides
    app.dependency_overrides[get_settings] = lambda: Settings(
        database_url="postgresql+psycopg://postgres:postgres@localhost:5432/terminal",
        oci_bucket=bucket,
        oci_config="dummy",
        oci_key="dummy",
    )
    app.dependency_overrides[get_fs] = lambda: mfs
    app.dependency_overrides[get_symbol_provider] = lambda: test_provider

    # Patch the external client in sync.py
    with patch("internal.features.symbols.sync.TradingViewScreenerClient") as MockTV:
        MockTV.return_value.fetch_symbols = AsyncMock(return_value=mock_symbols)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # 1. Trigger Sync
            sync_resp = await ac.post("/api/symbols/sync")
            assert sync_resp.status_code == 200
            assert sync_resp.json()["count"] == 1

            # Check if file was actually "written" to memory
            assert mfs.exists(f"{bucket}/symbols/symbols.json")

            # 2. Search for the symbol
            search_resp = await ac.get("/api/symbols/?q=RELIANCE&market=india")
            assert search_resp.status_code == 200
            results = search_resp.json()
            assert len(results) == 1
            assert results[0]["ticker"] == "NSE:RELIANCE"

            # 3. Check metadata
            meta_resp = await ac.get("/api/symbols/search_metadata")
            assert meta_resp.status_code == 200
            assert "india" in meta_resp.json()["markets"]

    app.dependency_overrides.clear()
