import asyncio
from typing import Callable, Awaitable
from models import Alert


class NotificationDispatcher:
    def __init__(self):
        self.queue: asyncio.Queue[Alert] = asyncio.Queue()
        self.handlers: list[Callable[[Alert], Awaitable[None]]] = []

    def register_handler(self, handler: Callable[[Alert], Awaitable[None]]):
        self.handlers.append(handler)

    async def dispatch_loop(self):
        while True:
            alert = await self.queue.get()
            await self._handle_alert(alert)

    async def enqueue(self, alert: Alert):
        await self.queue.put(alert)

    async def _handle_alert(self, alert: Alert):
        for handler in self.handlers:
            try:
                await handler(alert)
            except Exception as e:
                print(f"[Dispatcher] Error in handler: {e}")
