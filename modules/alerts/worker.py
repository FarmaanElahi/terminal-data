import asyncio
from modules.alerts.engine import AlertEngine


async def run_alerts_worker():
    engine = AlertEngine()
    await engine.start()
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(run_alerts_worker())
