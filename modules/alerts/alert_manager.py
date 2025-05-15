from typing import Callable, Dict, Optional
from models import Alert

# alert_manager.py

class AlertManager:
    def __init__(self):
        self._alerts_by_symbol: dict[str, list[Alert]] = {}

    def add_alert(self, alert: Alert):
        self._alerts_by_symbol.setdefault(alert.symbol, []).append(alert)

    def update_alert(self, alert: Alert):
        self.remove_alert_by_id(alert.id)
        self.add_alert(alert)

    def remove_alert(self, alert: Alert):
        alerts = self._alerts_by_symbol.get(alert.symbol)
        if alerts:
            self._alerts_by_symbol[alert.symbol] = [a for a in alerts if a.id != alert.id]
            if not self._alerts_by_symbol[alert.symbol]:
                del self._alerts_by_symbol[alert.symbol]

    def remove_alert_by_id(self, alert_id: str) -> Alert | None:
        for symbol, alerts in self._alerts_by_symbol.items():
            for alert in alerts:
                if alert.id == alert_id:
                    self._alerts_by_symbol[symbol].remove(alert)
                    if not self._alerts_by_symbol[symbol]:
                        del self._alerts_by_symbol[symbol]
                    return alert
        return None

    def get_alerts_for_symbol(self, symbol: str) -> list[Alert]:
        return self._alerts_by_symbol.get(symbol, [])

    def has_alerts_for_symbol(self, symbol: str) -> bool:
        return symbol in self._alerts_by_symbol and len(self._alerts_by_symbol[symbol]) > 0