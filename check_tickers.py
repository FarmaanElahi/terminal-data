import asyncio
from terminal.dependencies import _get_symbol_provider_instance


async def run():
    p = _get_symbol_provider_instance()
    syms = await p.search(limit=5)
    print("Tickers found:", [s["ticker"] for s in syms])


if __name__ == "__main__":
    asyncio.run(run())
