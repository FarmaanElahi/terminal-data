from typing import Any
from terminal.symbols.tradingview import TradingViewScreenerClient
from terminal.symbols.service import InMemorySymbolProvider


async def sync_symbols(fs: Any, bucket: str) -> int:
    """
    Syncs symbols from TradingView and persist them using InMemorySymbolProvider.
    """
    client = TradingViewScreenerClient()
    symbols = await client.fetch_symbols()

    # Pass dependencies to static persist method
    return await InMemorySymbolProvider.persist_symbols(
        fs=fs, bucket=bucket, symbols=symbols
    )
