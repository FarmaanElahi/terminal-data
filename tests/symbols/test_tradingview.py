import pytest
from terminal.tradingview import TradingView


@pytest.mark.asyncio
async def test_fetch_symbols_smoke():
    """
    Smoke test to ensure we can fetch symbols from TradingView.
    Note: This makes a real network request.
    """
    symbols = await TradingView().scanner.fetch_symbols(markets=["india"])
    assert len(symbols) > 0
    assert "ticker" in symbols[0]
    assert "name" in symbols[0]
    assert "typespecs" in symbols[0]
    assert "indexes" in symbols[0]
    print(f"Fetched {len(symbols)} symbols from India market")
