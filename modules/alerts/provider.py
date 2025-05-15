import asyncio
import datetime
import random
from abc import ABC, abstractmethod
from typing import Callable, Awaitable

from modules.alerts.models import ChangeUpdate

PriceCallback = Callable[[ChangeUpdate], Awaitable[None]]


class AlertDataProvider(ABC):
    @abstractmethod
    async def subscribe(self, symbol: str, callback: PriceCallback):
        pass

    @abstractmethod
    async def unsubscribe(self, symbol: str):
        pass

    @abstractmethod
    async def start(self):
        pass

    @abstractmethod
    async def stop(self):
        pass


class MockDataProvider(AlertDataProvider):
    def __init__(self):
        self.callbacks: dict[str, PriceCallback] = {}
        self.running = True

    async def start(self):
        asyncio.create_task(self._run())

    async def stop(self):
        self.running = False

    async def subscribe(self, symbol: str, callback: PriceCallback):
        self.callbacks[symbol] = callback
        print(f"[MockFeed] Subscribed to {symbol}")

    async def unsubscribe(self, symbol: str):
        if symbol in self.callbacks:
            del self.callbacks[symbol]
            print(f"[MockFeed] Unsubscribed from {symbol}")

    async def _run(self):
        while self.running:
            for symbol, cb in list(self.callbacks.items()):
                price = round(random.uniform(100, 200), 2)
                update = ChangeUpdate(symbol=symbol, ltq=10, ltp=price, ltt=datetime.datetime.now(datetime.UTC))
                print(f"Notifying update")
                print(update)
                await cb(update)
            await asyncio.sleep(1)
