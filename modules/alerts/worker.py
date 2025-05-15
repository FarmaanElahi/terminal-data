import asyncio
from engine import AlertEngine


async def main():
    engine = AlertEngine()
    await engine.start()
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())