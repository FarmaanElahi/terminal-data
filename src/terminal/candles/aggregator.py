"""Real-time candle aggregation from 1-minute WebSocket candles.

Consumes live 1-minute candles and produces higher-timeframe candles
(3m, 5m, 15m, 30m, 1h, 2h, 4h, etc.) by aggregating on-the-fly.

For daily candles from 1D WebSocket feed, passes through directly.
For multi-day timeframes (2D, 1W, 1M), aggregates from 1D feed.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from .models import tv_resolution_to_upstox

logger = logging.getLogger(__name__)

# IST offset in seconds (UTC+5:30)
_IST_OFFSET = 5 * 3600 + 30 * 60

# NSE market open in IST (09:15)
_MARKET_OPEN_IST_MINUTES = 9 * 60 + 15


@dataclass
class AggState:
    """Accumulation state for a single in-progress bar."""

    bar_start_ms: int = 0  # Start timestamp of current bar (ms)
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    volume: int = 0
    initialized: bool = False

    def update(self, o: float, h: float, low: float, c: float, v: int, ts_ms: int) -> None:
        if not self.initialized:
            self.open = o
            self.high = h
            self.low = low
            self.close = c
            self.volume = v
            self.bar_start_ms = ts_ms
            self.initialized = True
        else:
            self.high = max(self.high, h)
            self.low = min(self.low, low)
            self.close = c
            self.volume += v

    def to_dict(self, ticker: str, interval: str) -> dict[str, Any]:
        return {
            "ticker": ticker,
            "interval": interval,
            "timestamp": self.bar_start_ms,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
        }

    def reset(self) -> None:
        self.bar_start_ms = 0
        self.open = 0.0
        self.high = 0.0
        self.low = 0.0
        self.close = 0.0
        self.volume = 0
        self.initialized = False


@dataclass
class AggSubscription:
    """Tracks one (ticker, target_interval) aggregation."""

    ticker: str
    target_interval: str
    target_minutes: int  # Target bar size in minutes (0 for daily+)
    target_unit: str  # "minutes", "hours", "days", "weeks", "months"
    target_num: int
    state: AggState = field(default_factory=AggState)
    ref_count: int = 0
    queue: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(maxsize=100))


def _interval_to_minutes(unit: str, num: int) -> int:
    """Convert an interval unit+num to total minutes. Returns 0 for daily+."""
    if unit == "minutes":
        return num
    if unit == "hours":
        return num * 60
    return 0  # days, weeks, months — handled separately


def _bar_boundary_ms(ts_ms: int, bar_minutes: int) -> int:
    """Compute the bar start timestamp for an intraday bar.

    Uses modular arithmetic: a 5min bar starting at :00, :05, :10, etc.
    Respects IST timezone for bar alignment.
    """
    ts_sec = ts_ms // 1000
    # Convert to IST
    ist_sec = ts_sec + _IST_OFFSET
    # Seconds since midnight IST
    seconds_since_midnight = ist_sec % 86400
    bar_seconds = bar_minutes * 60
    # Floor to bar boundary
    aligned_seconds = (seconds_since_midnight // bar_seconds) * bar_seconds
    # Convert back to UTC ms
    midnight_utc = ist_sec - seconds_since_midnight - _IST_OFFSET
    return (midnight_utc + aligned_seconds) * 1000


def _daily_bar_boundary_ms(ts_ms: int) -> int:
    """Compute bar start for a daily bar (market open 09:15 IST)."""
    ts_sec = ts_ms // 1000
    ist_sec = ts_sec + _IST_OFFSET
    seconds_since_midnight = ist_sec % 86400
    midnight_utc = ist_sec - seconds_since_midnight - _IST_OFFSET
    # Market open at 09:15 IST
    market_open_sec = _MARKET_OPEN_IST_MINUTES * 60
    return (midnight_utc + market_open_sec) * 1000


class CandleAggregator:
    """Aggregates 1-minute candles into higher timeframes on-the-fly.

    Usage::

        aggregator = CandleAggregator()
        sub = aggregator.register("NSE:RELIANCE", "5")  # 5min
        aggregator.ingest("NSE:RELIANCE", "1m", candle_dict)
        # sub.queue has aggregated updates
    """

    def __init__(self) -> None:
        # (ticker, target_interval) -> AggSubscription
        self._subs: dict[tuple[str, str], AggSubscription] = {}

    def register(self, ticker: str, target_interval: str) -> AggSubscription:
        """Register interest in aggregated candles for (ticker, interval).

        Returns the subscription (with its queue) for consuming updates.
        Ref-counted: multiple callers share the same subscription.
        """
        key = (ticker, target_interval)

        if key in self._subs:
            self._subs[key].ref_count += 1
            return self._subs[key]

        upstox = tv_resolution_to_upstox(target_interval)
        if not upstox:
            raise ValueError(f"Cannot parse interval: {target_interval}")

        unit, num_str = upstox
        num = int(num_str)
        minutes = _interval_to_minutes(unit, num)

        sub = AggSubscription(
            ticker=ticker,
            target_interval=target_interval,
            target_minutes=minutes,
            target_unit=unit,
            target_num=num,
            ref_count=1,
        )
        self._subs[key] = sub
        logger.info("Aggregator registered: %s @ %s (%s/%d)", ticker, target_interval, unit, num)
        return sub

    def unregister(self, ticker: str, target_interval: str) -> None:
        """Decrement ref count; remove subscription if zero."""
        key = (ticker, target_interval)
        sub = self._subs.get(key)
        if not sub:
            return
        sub.ref_count -= 1
        if sub.ref_count <= 0:
            del self._subs[key]
            logger.info("Aggregator unregistered: %s @ %s", ticker, target_interval)

    def ingest(self, ticker: str, source_interval: str, candle: dict[str, Any]) -> None:
        """Feed a raw candle into the aggregator.

        Called whenever a 1-minute (or 1D for daily+ targets) candle arrives.
        Updates all relevant subscriptions for this ticker.
        """
        ts_ms = candle.get("timestamp", 0)
        o = candle.get("open", 0.0)
        h = candle.get("high", 0.0)
        low = candle.get("low", 0.0)
        c = candle.get("close", 0.0)
        v = int(candle.get("volume", 0))

        for key, sub in list(self._subs.items()):
            if sub.ticker != ticker:
                continue

            # Determine if this source candle is relevant for the target
            is_intraday_target = sub.target_minutes > 0
            is_minute_source = source_interval in ("1m", "1")
            is_daily_source = source_interval in ("1d", "1D", "D")

            if is_intraday_target and not is_minute_source:
                continue  # Intraday targets only consume minute candles
            if not is_intraday_target and not is_daily_source:
                # Daily+ targets consume daily candles
                # But also pass through if source matches target exactly
                if source_interval != sub.target_interval:
                    continue

            # Compute bar boundary
            if is_intraday_target:
                bar_start = _bar_boundary_ms(ts_ms, sub.target_minutes)
            else:
                bar_start = _daily_bar_boundary_ms(ts_ms)

            state = sub.state

            if not state.initialized:
                # First candle for this bar
                state.update(o, h, low, c, v, bar_start)
                self._emit(sub, complete=False)

            elif bar_start != state.bar_start_ms:
                # New bar boundary crossed — emit completed bar first
                self._emit(sub, complete=True)
                # Start new bar
                state.reset()
                state.update(o, h, low, c, v, bar_start)
                self._emit(sub, complete=False)

            else:
                # Same bar — accumulate
                state.update(o, h, low, c, v, ts_ms)
                self._emit(sub, complete=False)

    def _emit(self, sub: AggSubscription, complete: bool) -> None:
        """Push an update to the subscription queue."""
        data = sub.state.to_dict(sub.ticker, sub.target_interval)
        data["complete"] = complete
        try:
            sub.queue.put_nowait(data)
        except asyncio.QueueFull:
            # Drop oldest to keep queue flowing
            try:
                sub.queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            try:
                sub.queue.put_nowait(data)
            except asyncio.QueueFull:
                pass

    def has_subscription(self, ticker: str, target_interval: str) -> bool:
        return (ticker, target_interval) in self._subs
