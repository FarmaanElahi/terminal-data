import asyncio

from utils.scanner import run_full_scanner_build


async def main():
    await run_full_scanner_build()


if __name__ == "__main__":
    asyncio.run(main())
