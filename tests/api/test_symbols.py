import pytest
from terminal.main import api
from terminal.dependencies import get_fs, get_settings
from terminal.symbols import service as symbol_service
from terminal.config import Settings
from unittest.mock import AsyncMock, patch
from fsspec.implementations.memory import MemoryFileSystem


@pytest.fixture
def mock_fs():
    return MemoryFileSystem()


@pytest.fixture
def mock_settings():
    return Settings(
        env="dev",
        database_url="sqlite:///./test.db",
        oci_bucket="test-bucket",
        oci_config="config",
        oci_key="key",
        upstox_api_key="mock",
        upstox_api_secret="mock",
        upstox_redirect_uri="mock",
    )


@pytest.fixture(autouse=True)
def override_deps(mock_fs, mock_settings):
    api.dependency_overrides[get_fs] = lambda: mock_fs
    api.dependency_overrides[get_settings] = lambda: mock_settings
    yield
    api.dependency_overrides.clear()
    symbol_service._symbols_df = None  # clear cache between tests


@pytest.mark.asyncio
async def test_get_symbols_api(client, mock_fs, mock_settings):
    # 1. Seed data
    mock_data = [
        {
            "ticker": "NASDAQ:NVDA",
            "name": "nvidia",
            "market": "america",
            "type": "stock",
            "indexes": [{"name": "NASDAQ 100", "proname": "NDX"}],
            "typespecs": ["common"],
        }
    ]
    await symbol_service.refresh(mock_fs, mock_settings, mock_data)

    # 2. Test search via API
    response = await client.get("/api/v1/symbols/q?q=NVDA&market=america")
    assert response.status_code == 200
    data = response.json()
    items = data["items"]
    assert len(items) == 1
    assert items[0]["ticker"] == "NASDAQ:NVDA"


@pytest.mark.asyncio
async def test_get_symbols_metadata_api(client, mock_fs, mock_settings):
    # 1. Seed data
    mock_data = [
        {
            "ticker": "NSE:RELIANCE",
            "name": "RELIANCE INDUSTRIES",
            "market": "india",
            "type": "stock",
            "indexes": [{"name": "NIFTY 50", "proname": "NSE:NIFTY"}],
            "typespecs": ["common"],
        }
    ]
    await symbol_service.refresh(mock_fs, mock_settings, mock_data)

    # 2. Test metadata via API
    response = await client.get("/api/v1/symbols/search_metadata")
    assert response.status_code == 200
    data = response.json()
    assert "india" in data["markets"]
    assert "NIFTY 50" in data["indexes"]


@pytest.mark.asyncio
async def test_sync_symbols_api(client, mock_fs, mock_settings):
    """
    Test the sync API endpoint with mock sync logic.
    """
    mock_symbols = [
        {
            "ticker": "MOCK:TICKER",
            "name": "Mock Name",
            "market": "india",
            "type": "stock",
            "indexes": [{"name": "MOCK INDEX", "proname": "MOCK:IDX"}],
            "typespecs": ["common"],
        }
    ]

    # Patch sync_symbols in the router module
    with patch(
        "terminal.symbols.service.get_all_symbols_external", new_callable=AsyncMock
    ) as mocked_sync:
        mocked_sync.return_value = mock_symbols

        response = await client.post("/api/v1/symbols/sync")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "Sync complete"
        assert data["count"] == 1

        # Verify data was actually refreshed in memory FS
        import pandas as pd

        file_path = mock_settings.abs_file_path("symbols.parquet")
        assert mock_fs.exists(file_path)
        with mock_fs.open(file_path, "rb") as f:
            df = pd.read_parquet(f)
            assert len(df) == 1
            assert df.iloc[0]["ticker"] == "MOCK:TICKER"
