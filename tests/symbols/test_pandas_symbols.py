import pytest
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


@pytest.mark.asyncio
async def test_symbol_fts_search(mock_fs, mock_settings):
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
    await symbol_service.refresh(mock_fs, mock_settings, symbols)
    await symbol_service.init(mock_fs, mock_settings)

    # 2. Search by ticker (prefix) -> now regex/substring depending on implementation
    # Implementation uses str.contains
    results = await symbol_service.search(
        mock_fs, mock_settings, text="AA", market="america"
    )
    assert len(results) == 1
    assert results[0]["ticker"] == "AAPL"

    # 3. Search by name
    results = await symbol_service.search(
        mock_fs, mock_settings, text="Microsoft", market="america"
    )
    assert len(results) == 1
    assert results[0]["ticker"] == "MSFT"

    # 4. Search by partial name prefix
    results = await symbol_service.search(
        mock_fs, mock_settings, text="Relia", market="india"
    )
    assert len(results) == 1
    assert results[0]["ticker"] == "RELIANCE"

    # 5. Search with multiple terms
    results = await symbol_service.search(
        mock_fs, mock_settings, text="Tata Consu", market="india"
    )
    assert len(results) == 1
    assert results[0]["ticker"] == "TCS"

    # 6. Filter by index
    results = await symbol_service.search(
        mock_fs, mock_settings, index="NIFTY 50", market="india"
    )
    assert len(results) == 2
    tickers = {r["ticker"] for r in results}
    assert "RELIANCE" in tickers
    assert "TCS" in tickers


@pytest.mark.asyncio
async def test_get_metadata(mock_fs, mock_settings):
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
    await symbol_service.refresh(mock_fs, mock_settings, symbols)
    await symbol_service.init(mock_fs, mock_settings)

    metadata = await symbol_service.get_filter_metadata(mock_fs, mock_settings)
    assert "america" in metadata["markets"]
    assert "india" in metadata["markets"]
    assert "NASDAQ 100" in metadata["indexes"]
    assert "NIFTY 50" in metadata["indexes"]
    assert "stock" in metadata["types"]


@pytest.mark.asyncio
async def test_symbol_upsert_logic(mock_fs, mock_settings):
    # 1. Initial sync
    initial_symbols = [
        {
            "ticker": "AAPL",
            "name": "Apple",
            "type": "stock",
            "market": "america",
        }
    ]
    await symbol_service.refresh(mock_fs, mock_settings, initial_symbols)
    await symbol_service.init(mock_fs, mock_settings)

    symbol_data_1 = symbol_service._symbols_df
    assert len(symbol_data_1) == 1
    assert symbol_data_1.iloc[0]["name"] == "Apple"

    # 2. Sync with updated name for same ticker
    # Note: refresh with provided symbols completely overwrites CSV, it doesnt do merge in current implementation
    # since it assumes external source has the state of truth
    updated_symbols = [
        {
            "ticker": "AAPL",
            "name": "Apple Inc.",
            "type": "stock",
            "market": "america",
        }
    ]
    await symbol_service.refresh(mock_fs, mock_settings, updated_symbols)
    await symbol_service.init(mock_fs, mock_settings)

    # 3. Verify total count and updated data
    symbol_data_2 = symbol_service._symbols_df
    assert len(symbol_data_2) == 1
    assert symbol_data_2.iloc[0]["ticker"] == "AAPL"
    assert symbol_data_2.iloc[0]["name"] == "Apple Inc."
