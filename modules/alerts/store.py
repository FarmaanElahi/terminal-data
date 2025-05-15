# store.py

import asyncio
import os
from typing import Callable, Coroutine

from supabase import create_async_client, AsyncClient

from modules.alerts.models import Alert

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_KEY"]  # Use service role key


class AlertStore:
    def __init__(self):
        self.client: AsyncClient | None = None
        self.channel = None
        self.tbl = "alerts"

    async def _init_client(self):
        self.client = await create_async_client(SUPABASE_URL, SUPABASE_KEY)

    async def fetch_active_alerts(self) -> list[Alert]:
        if not self.client:
            await self._init_client()

        res = await self.client.table(self.tbl).select("*").eq("is_active", True).execute()
        return [Alert.model_validate(row) for row in res.data]

    async def mark_alert_triggered(self, alert_id: str):
        self.client.table("alerts").update({"is_active": False}).eq("id", alert_id).execute()

    async def subscribe_to_changes(
            self,
            on_insert: Callable[[Alert], Coroutine],
            on_update: Callable[[Alert], Coroutine],
            on_delete: Callable[[str], Coroutine]
    ):
        self.channel = self.client.channel("alerts:realtime")
        self.channel.on_postgres_changes("INSERT", table=self.tbl, schema="public", callback=lambda payload: self._handle_insert(payload, on_insert))
        self.channel.on_postgres_changes("UPDATE", table=self.tbl, schema="public", callback=lambda payload: self._handle_update(payload, on_update))
        self.channel.on_postgres_changes("DELETE", table=self.tbl, schema="public", callback=lambda payload: self._handle_delete(payload, on_delete))
        return await self.channel.subscribe()

    @staticmethod
    def _handle_insert(payload, on_insert):
        print(payload)
        alert_data = payload["new"]
        alert = Alert.model_validate(alert_data)
        asyncio.create_task(on_insert(alert))

    @staticmethod
    def _handle_update(payload, on_update):
        print(payload)
        alert_data = payload["new"]
        alert = Alert.model_validate(alert_data)
        asyncio.create_task(on_update(alert))

    @staticmethod
    def _handle_delete(payload, on_delete):
        print(payload)
        alert_id = payload["old"]["id"]
        asyncio.create_task(on_delete(alert_id))
