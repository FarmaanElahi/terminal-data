import pytest
from terminal.symbols.tradingview import TradingViewScreenerClient


@pytest.mark.asyncio
async def test_fetch_symbols_smoke():
    """
    Smoke test to ensure we can fetch symbols from TradingView.
    Note: This makes a real network request.
    """
    client = TradingViewScreenerClient()
    # Fetch only a small set if possible, but the API doesn't support small range easily in this call
    # We'll just verify it returns something
    symbols = await client.fetch_symbols(markets=["india"])
    assert len(symbols) > 0
    assert "ticker" in symbols[0]
    assert "name" in symbols[0]
    assert "typespecs" in symbols[0]
    assert "indexes" in symbols[0]
    print(f"Fetched {len(symbols)} symbols from India market")
