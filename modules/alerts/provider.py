import asyncio
import datetime
import random
from abc import ABC, abstractmethod
from typing import Callable, Awaitable

from modules.alerts.models import ChangeUpdate
from modules.core.provider.tradingview.quote_scaler import TradingViewScaler
from modules.core.provider.tradingview.quote_streamer import QuoteStreamEvent

PriceCallback = Callable[[ChangeUpdate], Awaitable[None]]


class AlertDataProvider(ABC):

    def __init__(self, callback: PriceCallback):
        super().__init__()
        self.cb = callback

    @abstractmethod
    async def subscribe(self, symbol: str):
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


class TradingViewProvider(AlertDataProvider):

    def __init__(self, cb: PriceCallback):
        super().__init__(cb)
        self.client = TradingViewScaler(["lp", "lp_time", "exchange", "pro_name", "short_name"])

    async def subscribe(self, symbol: str):
        await self.client.add_tickers([symbol])

    async def unsubscribe(self, symbol: str):
        await self.client.remove_tickers([symbol])

    async def start(self):
        await self.client.start()
        async for event_type, ticker, data in self.client.quote_events():
            if event_type == QuoteStreamEvent.QUOTE_UPDATE or event_type == QuoteStreamEvent.QUOTE_COMPLETED:
                d: dict = data
                update = ChangeUpdate(symbol=ticker, ltp=d['lp'], ltt=datetime.datetime.fromtimestamp(d['lp_time']), ltq=10)
                await self.cb(update)

    async def stop(self):
        await self.client.stop()


class MockDataProvider(AlertDataProvider):
    def __init__(self, cb: PriceCallback):
        super().__init__(cb)
        self.running = True
        self.tickers = set()

    async def start(self):
        asyncio.create_task(self._run())

    async def stop(self):
        self.running = False

    async def subscribe(self, symbol: str):
        print(f"[MockFeed] Subscribed to {symbol}")
        self.tickers.add(symbol)

    async def unsubscribe(self, symbol: str):
        if symbol in self.tickers:
            self.tickers.remove(symbol)
            print(f"[MockFeed] Unsubscribed from {symbol}")

    async def _run(self):
        while self.running:
            for symbol in list(self.tickers):
                price = round(random.uniform(100, 200), 2)
                update = ChangeUpdate(symbol=symbol, ltq=10, ltp=104000, ltt=datetime.datetime.now(datetime.UTC))
                print(f"Notifying update")
                print(update)
                await self.cb(update)
            await asyncio.sleep(1)
