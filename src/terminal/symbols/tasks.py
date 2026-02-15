from typing import Any
from terminal.tradingview import TradingView
from terminal.symbols.service import InMemorySymbolProvider


async def sync_symbols(fs: Any, bucket: str) -> int:
    """
    Syncs symbols from TradingView and persist them using InMemorySymbolProvider.
    """
    symbols = await TradingView().scanner.fetch_symbols()

    # Pass dependencies to static persist method
    return await InMemorySymbolProvider.persist_symbols(
        fs=fs, bucket=bucket, symbols=symbols
    )
