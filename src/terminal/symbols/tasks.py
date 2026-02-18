from typing import Any
from terminal.tradingview import TradingView


async def sync_symbols(fs: Any, bucket: str) -> list[dict[str, Any]]:
    """
    Syncs symbols from TradingView.
    """
    return await TradingView().scanner.fetch_symbols()
