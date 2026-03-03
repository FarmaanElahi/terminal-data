from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from terminal.candles.provider import CandleProvider


class Market(StrEnum):
    INDIA = "india"
    US = "us"


class Capability(StrEnum):
    REALTIME_CANDLES = "realtime_candles"
    ALERTS = "alerts"
    ORDER_MANAGEMENT = "order_management"
    POSITIONS = "positions"
    HOLDINGS = "holdings"


@dataclass(slots=True)
class BrokerAccountInfo:
    account_id: str | None = None
    account_label: str | None = None
    account_owner: str | None = None
    raw_profile: dict[str, Any] | None = None


class BrokerAdapter(ABC):
    provider_id: str
    display_name: str
    markets: list[Market]
    capabilities: list[Capability]

    @abstractmethod
    def build_auth_url(self) -> str:
        """Build provider OAuth authorization URL."""

    @abstractmethod
    async def exchange_code(self, code: str) -> str:
        """Exchange OAuth code for an access token."""

    @abstractmethod
    def is_configured(self) -> bool:
        """Whether this provider can be used on this server."""

    def create_candle_provider(
        self,
        token: str,
        feed: Any | None = None,
    ) -> "CandleProvider | None":
        """Build a candle provider for this adapter if supported."""
        return None

    def create_feed(self, token: str) -> Any | None:
        """Build a realtime feed instance for this adapter if supported."""
        return None

    @abstractmethod
    async def validate_token(self, token: str) -> bool:
        """Validate token authenticity/expiry for this adapter."""
        ...

    async def fetch_account_info(self, token: str) -> BrokerAccountInfo | None:
        """Fetch account profile details for a token, if supported."""
        return None

    # ── Alert CRUD (optional, for providers with Capability.ALERTS) ──

    async def list_alerts(self, token: str, status: str | None = None) -> list[dict]:
        """List alerts. Override in adapters that support alerts."""
        raise NotImplementedError(f"{self.provider_id} does not support alerts")

    async def create_alert(self, token: str, params: dict) -> dict:
        """Create an alert. Override in adapters that support alerts."""
        raise NotImplementedError(f"{self.provider_id} does not support alerts")

    async def modify_alert(self, token: str, alert_id: str, params: dict) -> dict:
        """Modify an alert. Override in adapters that support alerts."""
        raise NotImplementedError(f"{self.provider_id} does not support alerts")

    async def delete_alerts(self, token: str, alert_ids: list[str]) -> dict:
        """Delete one or more alerts. Override in adapters that support alerts."""
        raise NotImplementedError(f"{self.provider_id} does not support alerts")

    def supports(
        self,
        capability: Capability,
        market: Market | str | None = None,
    ) -> bool:
        if capability not in self.capabilities:
            return False
        if market is None:
            return True

        if isinstance(market, str):
            try:
                market = Market(market)
            except ValueError:
                return False

        return market in self.markets
