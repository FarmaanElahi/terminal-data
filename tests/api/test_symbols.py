import pytest
from terminal.symbols.models import Symbol
from terminal.symbols import service as symbol_service
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_get_symbols_api(client, session):
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
    await symbol_service.refresh(session, mock_data)

    # 2. Test search via API
    response = await client.get("/api/v1/symbols/?q=NVDA&market=america")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["ticker"] == "NASDAQ:NVDA"
    assert data[0]["indexes"][0]["name"] == "NASDAQ 100"


@pytest.mark.asyncio
async def test_get_symbols_metadata_api(client, session):
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
    await symbol_service.refresh(session, mock_data)

    # 2. Test metadata via API
    response = await client.get("/api/v1/symbols/search_metadata")
    assert response.status_code == 200
    data = response.json()
    assert "india" in data["markets"]
    assert "NIFTY 50" in data["indexes"]


@pytest.mark.asyncio
async def test_sync_symbols_api(client, session):
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
        "terminal.symbols.router.sync_symbols", new_callable=AsyncMock
    ) as mocked_sync:
        mocked_sync.return_value = mock_symbols

        response = await client.post("/api/v1/symbols/sync")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "Sync complete"
        assert data["count"] == 1

        # Verify data was actually refreshed in DB
        from sqlmodel import select

        symbols_in_db = session.exec(select(Symbol)).all()
        assert len(symbols_in_db) == 1
        assert symbols_in_db[0].ticker == "MOCK:TICKER"
        assert symbols_in_db[0].indexes[0]["name"] == "MOCK INDEX"
        assert symbols_in_db[0].typespecs == ["common"]
