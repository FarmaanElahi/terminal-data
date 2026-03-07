import pytest
import pandas as pd
from terminal.lists import service as lists_service
from terminal.symbols import service as symbols_service


@pytest.fixture(autouse=True)
def mock_symbols_cache():
    """Ensure symbols_df is initialized for tests."""
    symbols_service._symbols_df = pd.DataFrame(
        [
            {
                "ticker": "AAPL",
                "market": "usa",
                "type": "stock",
                "exchange": "NASDAQ",
                "indexes": [],
                "isin": None,
                "typespecs": [],
            },
            {
                "ticker": "RELIANCE",
                "market": "india",
                "type": "stock",
                "exchange": "NSE",
                "indexes": [{"name": "NIFTY 50"}],
                "isin": None,
                "typespecs": [],
            },
            {
                "ticker": "TCS",
                "market": "india",
                "type": "stock",
                "exchange": "NSE",
                "indexes": [{"name": "NIFTY 50"}],
                "isin": None,
                "typespecs": [],
            },
        ]
    )
    yield
    symbols_service._symbols_df = None


@pytest.mark.asyncio
async def test_get_all_system_lists():
    # We need a dummy fs and settings
    class MockFS:
        pass

    class MockSettings:
        pass

    system_lists = await lists_service.get_all_system_lists(MockFS(), MockSettings())

    # india and usa markets, NSE exchange, plus NIFTY 50 index
    assert len(system_lists) == 4
    ids = [l.id for l in system_lists]
    assert "sys:mkt:india" in ids
    assert "sys:mkt:usa" in ids
    assert "sys:exc:NSE" in ids
    assert "sys:idx:NIFTY 50" in ids

    names = [l.name for l in system_lists]
    assert "India Stock" in names
    assert "NSE Stock" in names
    assert "NIFTY 50 Stock" in names


@pytest.mark.asyncio
async def test_get_system_list_symbols(session):
    class MockFS:
        pass

    class MockSettings:
        pass

    lst = lists_service.get_system_list_by_id("sys:mkt:india")
    symbols = await lists_service.get_symbols_async(
        session, lst, "user", MockFS(), MockSettings()
    )
    assert set(symbols) == {"RELIANCE", "TCS"}

    lst_idx = lists_service.get_system_list_by_id("sys:idx:NIFTY 50")
    symbols_idx = await lists_service.get_symbols_async(
        session, lst_idx, "user", MockFS(), MockSettings()
    )
    assert set(symbols_idx) == {"RELIANCE", "TCS"}


@pytest.mark.asyncio
async def test_router_all_lists_includes_system(client, token):
    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.get("/api/v1/lists", headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    # Should have default color lists + system lists
    system_lists = [lst_item for lst_item in data if lst_item["type"] == "system"]
    assert len(system_lists) >= 3
    assert any(lst_item["id"] == "sys:mkt:india" for lst_item in system_lists)


@pytest.mark.asyncio
async def test_router_get_system_list(client, token):
    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.get("/api/v1/lists/sys:mkt:india", headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    assert data["id"] == "sys:mkt:india"
    assert "RELIANCE" in data["symbols"]
    assert "TCS" in data["symbols"]
    assert data["type"] == "system"
