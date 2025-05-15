from modules.alerts.alert_manager import AlertManager
from modules.alerts.dispatcher_queue import NotificationDispatcher
from modules.alerts.evaluator import evaluate_alert
from modules.alerts.models import Alert, ChangeUpdate
from modules.alerts.store import AlertStore
from modules.alerts.provider import MockDataProvider


class AlertEngine:
    def __init__(self):
        self.alert_manager = AlertManager()
        self.dispatcher = NotificationDispatcher()
        self.store = AlertStore()
        self.data_provider = MockDataProvider()

    async def start(self):
        print("[Engine] Starting alert engine...")
        await self._sync_existing_alerts()
        await self._subscribe_to_alert_changes()
        await self.data_provider.start()

    async def _sync_existing_alerts(self):
        print("[Engine] Loading active alerts from store...")
        alerts = await self.store.fetch_active_alerts()
        for alert in alerts:
            self.alert_manager.add_alert(alert)
            await self.data_provider.subscribe(alert.symbol, self._on_price_tick)

    async def _subscribe_to_alert_changes(self):
        print("[Engine] Subscribing to Supabase Realtime...")
        await self.store.subscribe_to_changes(
            on_insert=self._handle_insert,
            on_update=self._handle_update,
            on_delete=self._handle_delete
        )

    async def _on_price_tick(self, update: ChangeUpdate):
        alerts = self.alert_manager.get_alerts_for_symbol(update.symbol)
        if not alerts:
            return

        for alert in list(alerts):  # Safe to mutate original list during iteration
            if evaluate_alert(alert, update):
                print(f"[Trigger] {update.symbol} @ {update.ltt} | Alert {alert.id}")
                await self.dispatcher.enqueue(alert)
                await self.store.mark_alert_triggered(alert.id)
                self.alert_manager.remove_alert(alert)

        # Cleanup if no more alerts for the symbol
        if not self.alert_manager.has_alerts_for_symbol(update.symbol):
            await self.data_provider.unsubscribe(update.symbol)

    async def _handle_insert(self, alert: Alert):
        print(f"[Insert] Alert {alert.id}")
        self.alert_manager.add_alert(alert)
        await self.data_provider.subscribe(alert.symbol)

    async def _handle_update(self, alert: Alert):
        print(f"[Update] Alert {alert.id}")
        self.alert_manager.update_alert(alert)
        await self.data_provider.subscribe(alert.symbol)

    async def _handle_delete(self, alert_id: str):
        print(f"[Delete] Alert {alert_id}")
        removed = self.alert_manager.remove_alert_by_id(alert_id)
        if removed and not self.alert_manager.has_alerts_for_symbol(removed.symbol):
            await self.data_provider.unsubscribe(removed.symbol)
