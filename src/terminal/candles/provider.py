"""Abstract base class for candle data providers.

Each market (India, America, etc.) has its own concrete provider that knows
how to fetch historical/intraday candles and optionally stream real-time
updates for instruments in that market.
"""

from abc import ABC, abstractmethod
from datetime import date

from typing import Any, AsyncGenerator
from .models import Candle


class CandleProvider(ABC):
    """Abstract candle data provider.

    Concrete implementations handle a specific market's data source
    (e.g. Upstox for India, a future provider for America).
    """

    @property
    @abstractmethod
    def market(self) -> str:
        """Market identifier this provider handles, e.g. ``"india"`` or ``"america"``."""
        ...

    @abstractmethod
    def get_candle_feed_token(self, ticker: str) -> str | None:
        """Convert a terminal ticker to a provider-specific feed token.

        Args:
            ticker: Terminal format ``EXCHANGE:SYMBOL``

        Returns:
            Provider-specific token (e.g. ``NSE_EQ|INE002A01018`` for Upstox).
            Returns None if the ticker cannot be resolved.
        """
        ...

    @abstractmethod
    async def start_feed(self) -> None:
        """Start the real-time feed connection."""
        ...

    @abstractmethod
    async def stop_feed(self) -> None:
        """Stop the real-time feed connection."""
        ...

    @abstractmethod
    async def get_candles(
        self,
        ticker: str,
        interval: str,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> list[Candle]:
        """Fetch candle data.

        Concrete implementations should handle the logic of switching between
        intraday vs historical data sources if necessary.

        Args:
            ticker: Terminal format ``EXCHANGE:SYMBOL``
            interval: Candle interval
            from_date: Start date (optional)
            to_date: End date (optional)

        Returns:
            Candles sorted chronologically (oldest first).
        """
        ...

    @abstractmethod
    async def subscribe(self, ticker: str) -> None:
        """Subscribe to real-time updates for a ticker."""
        ...

    @abstractmethod
    async def unsubscribe(self, ticker: str) -> None:
        """Unsubscribe from real-time updates for a ticker."""
        ...

    @abstractmethod
    async def on_update(self) -> AsyncGenerator[dict[str, Any], None]:
        """Async generator yielding real-time candle updates for this provider.

        Updates should be yielded as dictionaries following the candle model,
        including a "ticker" field.
        """
        ...

    @abstractmethod
    async def close(self) -> None:
        """Release any held resources (HTTP clients, feeds, etc.)."""
        ...
