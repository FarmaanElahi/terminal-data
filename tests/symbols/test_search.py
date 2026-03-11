import pytest
import pytest_asyncio
from terminal.symbols import service as symbol_service
from terminal.config import Settings
from fsspec.implementations.memory import MemoryFileSystem


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
def setup_teardown():
    yield
    symbol_service._symbols_df = None


@pytest_asyncio.fixture
async def seeded_fs_settings(mock_fs, mock_settings):
    """
    Creates a memory filesystem with mock data for testing search logic.
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

    await symbol_service.refresh(mock_fs, mock_settings, mock_data)
    await symbol_service.init(mock_fs, mock_settings)
    return mock_fs, mock_settings


@pytest.mark.asyncio
async def test_search_symbols_query(seeded_fs_settings):
    fs, settings = seeded_fs_settings
    # Search by ticker
    results = await symbol_service.search(fs, settings, text="NVDA", market="america")
    assert len(results) == 1
    assert results[0]["ticker"] == "NASDAQ:NVDA"

    # Search by name
    results = await symbol_service.search(fs, settings, text="RELIANCE", market="india")
    assert len(results) == 1
    assert "RELIANCE" in results[0]["name"]


@pytest.mark.asyncio
async def test_search_symbols_type(seeded_fs_settings):
    fs, settings = seeded_fs_settings
    results = await symbol_service.search(
        fs, settings, item_type="fund", market="america"
    )
    assert len(results) == 1
    assert results[0]["ticker"] == "NYSE:SPY"

    results = await symbol_service.search(
        fs, settings, item_type="stock", market="america"
    )
    assert len(results) == 1
    assert results[0]["ticker"] == "NASDAQ:NVDA"


@pytest.mark.asyncio
async def test_search_symbols_market_default(seeded_fs_settings):
    fs, settings = seeded_fs_settings
    results = await symbol_service.search(fs, settings, text="TCS")
    assert len(results) == 1
    assert results[0]["ticker"] == "NSE:TCS"


@pytest.mark.asyncio
async def test_search_symbols_index(seeded_fs_settings):
    fs, settings = seeded_fs_settings
    results = await symbol_service.search(
        fs, settings, index="NIFTY 50", market="india"
    )
    assert len(results) == 2  # RELIANCE and TCS

    results = await symbol_service.search(fs, settings, index="CNX IT", market="india")
    assert len(results) == 1
    assert results[0]["ticker"] == "NSE:TCS"


@pytest.mark.asyncio
async def test_get_search_metadata(seeded_fs_settings):
    fs, settings = seeded_fs_settings
    metadata = await symbol_service.get_filter_metadata(fs, settings)
    assert "india" in metadata["markets"]
    assert "america" in metadata["markets"]
    assert "stock" in metadata["types"]
    assert "fund" in metadata["types"]
    assert "NIFTY 50" in metadata["indexes"]
    assert "NASDAQ 100" in metadata["indexes"]
