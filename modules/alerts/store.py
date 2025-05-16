# store.py

import asyncio
import os
from typing import Callable, Coroutine, Any
import logging
from supabase import create_async_client, AsyncClient

from modules.alerts.models import Alert

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_KEY"]  # Use service role key

logger = logging.getLogger(__name__)


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

    async def mark_alert_triggered(self, alert_id: str, price: float):
        await self.client.table("alerts").update({
            "is_active": False,
            "last_triggered_at": "now()",
            "last_triggered_price": price,
            "updated_at": "now()",
        }).eq("id", alert_id).execute()

    async def subscribe_to_changes(
            self,
            on_insert: Callable[[Alert], Coroutine],
            on_update: Callable[[Alert], Coroutine],
            on_delete: Callable[[Alert], Coroutine]
    ):
        self.channel = self.client.channel("alerts:realtime")
        self.channel.on_postgres_changes("INSERT", table=self.tbl, schema="public", callback=lambda payload: self._handle_insert(payload, on_insert))
        self.channel.on_postgres_changes("UPDATE", table=self.tbl, schema="public", callback=lambda payload: self._handle_update(payload, on_update, on_delete))
        return await self.channel.subscribe()

    @staticmethod
    def _handle_insert(payload: dict[str, Any], on_insert):
        alert_data = payload.get("data", {}).get("record")
        if not alert_data:
            return
        logger.debug(f"Insert: alert {alert_data}")
        alert = Alert.model_validate(alert_data)
        asyncio.create_task(on_insert(alert))

    @staticmethod
    def _handle_update(payload: dict[str, Any], on_update, _on_delete):
        alert_data = payload.get("data", {}).get("record")
        if not alert_data:
            return
        alert = Alert.model_validate(alert_data)

        # Delete are represented as a deleted_at field,
        # Delete doesn't delete alert, it will be automatically cleared in the database
        if alert.deleted_at is not None or not alert.is_active:
            logger.debug(f"DELETE: alert {alert_data}")
            asyncio.create_task(_on_delete(alert))
            return

        logger.debug(f"UPDATE: alert {alert_data}")
        asyncio.create_task(on_update(alert))
