import pytest
from unittest.mock import patch, AsyncMock
from terminal.symbols.models import Symbol
from sqlalchemy import select


@pytest.mark.asyncio
async def test_full_sync_and_search_flow(client, session):
    """
    Tests the full flow from fetching (mocked) to search via API with DB.
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
    with patch("terminal.symbols.tasks.TradingView") as MockTV:
        MockTV.return_value.scanner.fetch_symbols = AsyncMock(return_value=mock_symbols)

        # 1. Trigger Sync via API
        sync_resp = await client.post("/api/v1/symbols/sync")
        assert sync_resp.status_code == 200
        assert sync_resp.json()["count"] == 1

        # 2. Verify data in DB
        symbols_in_db = list(session.execute(select(Symbol)).scalars().all())
        assert len(symbols_in_db) == 1
        assert symbols_in_db[0].ticker == "NSE:RELIANCE"
        assert symbols_in_db[0].indexes[0]["name"] == "NIFTY 50"

        # 3. Search for the symbol via API
        search_resp = await client.get("/api/v1/symbols/?q=RELIANCE&market=india")
        assert search_resp.status_code == 200
        results = search_resp.json()
        assert len(results) == 1
        assert results[0]["ticker"] == "NSE:RELIANCE"

        # 4. Check metadata via API
        meta_resp = await client.get("/api/v1/symbols/search_metadata")
        assert meta_resp.status_code == 200
        assert "india" in meta_resp.json()["markets"]
        assert "NIFTY 50" in meta_resp.json()["indexes"]
