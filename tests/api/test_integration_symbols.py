import pytest
from unittest.mock import patch, AsyncMock
from terminal.main import api
from terminal.dependencies import get_fs, get_settings
from terminal.config import Settings
from terminal.symbols import service as symbol_service
from fsspec.implementations.memory import MemoryFileSystem
import pandas as pd


@pytest.fixture
def mock_fs():
    return MemoryFileSystem()


@pytest.fixture
def mock_settings():
    return Settings(
        env="dev",
        db_scheme="sqlite",
        db_name="./test.db",
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
    symbol_service._symbols_df = None


@pytest.mark.asyncio
async def test_full_sync_and_search_flow(client, mock_fs, mock_settings):
    """
    Tests the full flow from fetching (mocked) to search via API with Pandas.
    """
    mock_symbols = [
        {
            "ticker": "NSE:RELIANCE",
            "name": "RELIANCE INDUSTRIES",
            "country": "India",
            "market": "india",
            "type": "stock",
            "isin": "INE002A01018",
            "indexes": [{"name": "NIFTY 50", "proname": "NSE:NIFTY"}],
            "typespecs": ["common"],
        }
    ]

    # Patch the external client in tasks.py
    with patch(
        "terminal.symbols.service.get_all_symbols_external", new_callable=AsyncMock
    ) as mocked_get_symbols:
        mocked_get_symbols.return_value = mock_symbols

        # 1. Trigger Sync via API
        sync_resp = await client.post("/api/v1/symbols/sync")
        assert sync_resp.status_code == 200
        assert sync_resp.json()["count"] == 1

        # 2. Verify data in mock FS
        file_path = mock_settings.abs_file_path("symbols.parquet")
        assert mock_fs.exists(file_path)
        with mock_fs.open(file_path, "rb") as f:
            df = pd.read_parquet(f)
            assert len(df) == 1
            assert df.iloc[0]["ticker"] == "NSE:RELIANCE"

        # 3. Search for the symbol via API
        search_resp = await client.get("/api/v1/symbols/q?q=RELIANCE&market=india")
        assert search_resp.status_code == 200
        results = search_resp.json()
        items = results["items"]
        assert len(items) == 1
        assert items[0]["ticker"] == "NSE:RELIANCE"

        # 4. Check metadata via API
        meta_resp = await client.get("/api/v1/symbols/search_metadata")
        assert meta_resp.status_code == 200
        assert "india" in meta_resp.json()["markets"]
        assert "NIFTY 50" in meta_resp.json()["indexes"]
