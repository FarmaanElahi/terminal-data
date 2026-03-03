from __future__ import annotations

from terminal.broker.adapter import BrokerAdapter, Capability, Market
from terminal.broker.adapters import KiteAdapter, UpstoxAdapter


class BrokerRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, BrokerAdapter] = {}

    def register(self, adapter: BrokerAdapter) -> None:
        self._adapters[adapter.provider_id] = adapter

    def get(self, provider_id: str) -> BrokerAdapter | None:
        return self._adapters.get(provider_id)

    def all(self) -> list[BrokerAdapter]:
        return list(self._adapters.values())

    def configured(self) -> list[BrokerAdapter]:
        return [adapter for adapter in self._adapters.values() if adapter.is_configured()]

    def for_capability(
        self,
        capability: Capability,
        market: Market | str | None = None,
    ) -> list[BrokerAdapter]:
        return [
            adapter
            for adapter in self.configured()
            if adapter.supports(capability=capability, market=market)
        ]


broker_registry = BrokerRegistry()
broker_registry.register(UpstoxAdapter())
broker_registry.register(KiteAdapter())
