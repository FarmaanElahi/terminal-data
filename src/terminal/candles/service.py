"""CandleManager — multi-market candle data orchestrator.

Routes candle requests to the correct provider based on the exchange
prefix of the ticker (e.g. NSE → India/Upstox, NASDAQ → America).
Also manages real-time WebSocket feed subscriptions and candle aggregation.
"""

import asyncio
import logging
from datetime import date
from typing import Any, AsyncGenerator

from .aggregator import CandleAggregator, AggSubscription
from .models import Candle
from .provider import CandleProvider

logger = logging.getLogger(__name__)

# Exchange → market mapping
EXCHANGE_MARKET_MAP: dict[str, str] = {
    "NSE": "india",
    "BSE": "india",
    "NASDAQ": "america",
    "NYSE": "america",
    "AMEX": "america",
}


def detect_market(ticker: str) -> str:
    """Detect the market from a terminal ticker's exchange prefix.

    Args:
        ticker: Terminal format ``EXCHANGE:SYMBOL`` (e.g. ``NSE:RELIANCE``)

    Returns:
        Market identifier (``"india"``, ``"america"``). Defaults to ``"india"``.
    """
    exchange = ticker.split(":")[0] if ":" in ticker else ""
    return EXCHANGE_MARKET_MAP.get(exchange, "india")


class CandleManager:
    """Manages candle data retrieval across multiple market providers.

    Provides:
    - ``get_candles()``: fetch candles via the correct market provider
    - ``subscribe()``: stream real-time candle updates from WebSocket
    - ``on_update()``: async generator for consuming updates
    """

    def __init__(
        self,
        providers: dict[str, CandleProvider] | None = None,
    ) -> None:
        self._providers: dict[str, CandleProvider] = providers or {}
        self._update_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._stop_event = asyncio.Event()
        self._listener_tasks: dict[str, asyncio.Task] = {}
        self._aggregator = CandleAggregator()
        self._aggregator_dispatch_task: asyncio.Task | None = None
        # Start listeners for existing providers if loop is running
        try:
            asyncio.get_running_loop()
            for market, provider in self._providers.items():
                self._start_listener(market, provider)
        except RuntimeError:
            pass

    def _start_listener(self, market: str, provider: CandleProvider) -> None:
        """Start a background task to listen to a provider's update stream."""
        if market in self._listener_tasks:
            self._listener_tasks[market].cancel()

        coro = self._listen_to_provider(market, provider)
        try:
            self._listener_tasks[market] = asyncio.create_task(coro)
        except RuntimeError:
            coro.close()
            logger.debug("No event loop running, deferring listener for %s", market)

    async def _listen_to_provider(self, market: str, provider: CandleProvider) -> None:
        """Background loop piping provider updates into the manager's queue."""
        try:
            async for update in provider.on_update():
                await self._update_queue.put(update)
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Error in candle listener for market: %s", market)

    def register_provider(self, provider: CandleProvider) -> None:
        """Register a candle provider for its market."""
        self._providers[provider.market] = provider
        self._start_listener(provider.market, provider)
        logger.info("Registered candle provider for market=%s", provider.market)

    def get_provider_for_ticker(self, ticker: str) -> CandleProvider | None:
        """Get the correct provider based on a ticker's exchange prefix."""
        market = detect_market(ticker)
        return self._providers.get(market)

    # ------------------------------------------------------------------
    # Historical / Intraday
    # ------------------------------------------------------------------

    async def get_candles(
        self,
        ticker: str,
        interval: str,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> list[Candle]:
        """Fetch candles for an instrument using the correct market provider."""
        provider = self.get_provider_for_ticker(ticker)
        if not provider:
            logger.error("No candle provider registered for ticker: %s", ticker)
            return []

        return await provider.get_candles(ticker, interval, from_date, to_date)

    # ------------------------------------------------------------------
    # Real-time streaming
    # ------------------------------------------------------------------

    async def start_feed(self) -> None:
        """Start all registered provider feeds, listeners, and aggregator dispatch."""
        self._stop_event.clear()
        for market, provider in self._providers.items():
            if (
                market not in self._listener_tasks
                or self._listener_tasks[market].done()
            ):
                self._start_listener(market, provider)
            await provider.start_feed()

        # Start aggregator dispatch task
        if not self._aggregator_dispatch_task or self._aggregator_dispatch_task.done():
            self._aggregator_dispatch_task = asyncio.create_task(
                self._aggregator_dispatch_loop()
            )

    async def stop_feed(self) -> None:
        """Stop all registered provider feeds."""
        self._stop_event.set()
        for provider in self._providers.values():
            await provider.stop_feed()

    async def subscribe(self, ticker: str) -> None:
        """Subscribe to real-time updates for a ticker via its provider."""
        provider = self.get_provider_for_ticker(ticker)
        if provider:
            await provider.subscribe(ticker)

    async def unsubscribe(self, ticker: str) -> None:
        """Unsubscribe from real-time updates for a ticker via its provider."""
        provider = self.get_provider_for_ticker(ticker)
        if provider:
            await provider.unsubscribe(ticker)

    async def on_candle_update(self) -> AsyncGenerator[dict[str, Any], None]:
        """Async generator yielding real-time candle updates.

        Each yield is a dict:
        ``{"ticker": str, "interval": str, "open": ..., "high": ..., ...}``
        """
        while not self._stop_event.is_set():
            try:
                update = await asyncio.wait_for(self._update_queue.get(), timeout=1.0)
                yield update
            except asyncio.TimeoutError:
                continue

    # ------------------------------------------------------------------
    # Candle Aggregation
    # ------------------------------------------------------------------

    def subscribe_aggregated(
        self, ticker: str, interval: str
    ) -> AggSubscription:
        """Subscribe to aggregated candles for a (ticker, interval) pair.

        Returns an AggSubscription with a queue that yields aggregated updates.
        The aggregator is lazy: it only aggregates for intervals with active subscribers.
        """
        return self._aggregator.register(ticker, interval)

    def unsubscribe_aggregated(self, ticker: str, interval: str) -> None:
        """Unsubscribe from aggregated candles."""
        self._aggregator.unregister(ticker, interval)

    async def _aggregator_dispatch_loop(self) -> None:
        """Feed raw candle updates from providers into the aggregator."""
        try:
            while not self._stop_event.is_set():
                try:
                    update = await asyncio.wait_for(
                        self._update_queue.get(), timeout=1.0
                    )
                    # Feed into aggregator for any subscribed higher-timeframe targets
                    self._aggregator.ingest(
                        update.get("ticker", ""),
                        update.get("interval", ""),
                        update,
                    )
                except asyncio.TimeoutError:
                    continue
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Error in aggregator dispatch loop")

    async def close(self) -> None:
        """Clean up all resources and listeners."""
        await self.stop_feed()
        if self._aggregator_dispatch_task:
            self._aggregator_dispatch_task.cancel()
        for task in self._listener_tasks.values():
            task.cancel()
        for provider in self._providers.values():
            await provider.close()

    @property
    def has_feed(self) -> bool:
        """Whether any provider has a real-time feed configured."""
        return any(getattr(p, "has_feed", False) for p in self._providers.values())

    async def attach_provider_feed(self, market: str, feed) -> None:
        """Attach a shared feed to an existing provider (hot-plug after token arrives)."""
        provider = self._providers.get(market)
        if provider and hasattr(provider, "attach_feed"):
            await provider.attach_feed(feed)
