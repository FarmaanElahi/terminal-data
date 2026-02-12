import asyncio
import os
from typing import Callable, Awaitable
from modules.alerts.models import Alert
import httpx


class NotificationDispatcher:
    def __init__(self):
        self.queue: asyncio.Queue[Alert] = asyncio.Queue()
        self.handlers: list[Callable[[Alert], Awaitable[None]]] = []
        self.handlers.append(webhook_handler)

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


ALERT_WEBOOK_URL = os.environ.get("ALERT_WEBOOK_URL")
if ALERT_WEBOOK_URL is None:
    raise ValueError("ALERT_WEBOOK_URL environment variable not set")


async def webhook_handler(alert: Alert):
    async  with httpx.AsyncClient() as client:
        response = await client.post(
            ALERT_WEBOOK_URL,
            json={"alert": alert.model_dump(mode='json')},
        )
        print(response.text)
        if response.status_code != 200:
            print(f"[Dispatcher] Error in webhook: {response.text}")
            return
