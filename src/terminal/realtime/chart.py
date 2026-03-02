import asyncio
import logging
from datetime import date, datetime, timezone
from typing import Any

from terminal.candles.models import tv_resolution_to_upstox
from terminal.candles.service import CandleManager
from terminal.symbols.service import get_symbol
from terminal.realtime.models import (
    ChartCandleData,
    ChartParams,
    SymbolResolvedData,
    SymbolResolvedResponse,
    ResolveSymbolRequest,
    ChartSeriesResponse,
    ChartUpdateResponse,
    ClientMessage,
    CreateChartRequest,
    ModifyChartRequest,
    GetBarRequest,
    SubscribeBarRequest,
    UnsubscribeBarRequest,
)

logger = logging.getLogger(__name__)


class ChartSession:
    """Manages a single chart session via WebSockets.

    Responsible for:
    - Resolving symbol metadata via symbols_service.
    - Fetching historical candles via CandleManager.
    - Streaming real-time updates.
    """

    def __init__(
        self,
        session_id: str,
        realtime: Any,
        candle_manager: CandleManager,
    ) -> None:
        self.session_id = session_id
        self.realtime = realtime
        self.candle_manager = candle_manager
        self._streaming_tasks: dict[str, asyncio.Task] = {}  # series_id -> task
        self._symbol: str | None = None

    async def handle(self, msg: ClientMessage) -> None:
        """Handle incoming chart requests."""
        if isinstance(msg, CreateChartRequest):
            session_id, params = msg.p
            self.session_id = session_id
            logger.debug("Create chart session: %s", session_id)
            if params:
                await self._load_chart(params)
        elif isinstance(msg, ResolveSymbolRequest):
            _, ticker = msg.p
            logger.debug("Resolve symbol: %s", ticker)
            await self._resolve_symbol(ticker)
        elif isinstance(msg, ModifyChartRequest):
            _, params = msg.p
            logger.debug("Modify chart: %s", params)
            await self._load_chart(params)
        elif isinstance(msg, GetBarRequest):
            _, params = msg.p
            logger.debug("Get bar: %s", params)
            await self._get_bar(params)
        elif isinstance(msg, SubscribeBarRequest):
            _, params = msg.p
            logger.debug("Subscribe bar: %s", params)
            await self._subscribe_bar(params)
        elif isinstance(msg, UnsubscribeBarRequest):
            _, series_id = msg.p
            await self._unsubscribe_bar(series_id)

    async def _resolve_symbol(self, ticker: str) -> None:
        """Resolve symbol metadata and emit symbol_resolved."""
        sym = get_symbol(ticker)
        if not sym:
            await self.realtime.send_error(f"Symbol not found: {ticker}")
            return

        resolved = SymbolResolvedData(
            name=sym.get("name", ticker),
            ticker=ticker,
            description=sym.get("name"),
            type=sym.get("type", "stock"),
            exchange=ticker.split(":")[0] if ":" in ticker else "",
            timezone="Asia/Kolkata",  # Local exchange timezone
            logo_urls=(
                [f"https://s3-symbol-logo.tradingview.com/{sym['logo']}.svg"]
                if sym.get("logo")
                else None
            ),
            session=sym.get("session", "0915-1530"),
            has_intraday=True,
            has_daily=True,
            has_weekly_and_monthly=True,
        )
        await self.realtime.send(SymbolResolvedResponse(p=(self.session_id, resolved)))

    async def _get_bar(self, params: ChartParams) -> None:
        """Just an alias for _load_chart for now, but explicitly for get_bar msg."""
        await self._load_chart(params)

    async def _subscribe_bar(self, params: ChartParams) -> None:
        """Subscribe to a series."""
        series_id = params.series_id or f"{params.symbol}-{params.interval}"
        if series_id in self._streaming_tasks:
            return  # Already streaming this series

        task = asyncio.create_task(
            self._stream_loop(params.symbol, params.interval, series_id)
        )
        self._streaming_tasks[series_id] = task

    async def _unsubscribe_bar(self, series_id: str) -> None:
        """Unsubscribe from a series."""
        task = self._streaming_tasks.pop(series_id, None)
        if task:
            task.cancel()

    async def _load_chart(self, params: ChartParams) -> None:
        """Fetch candles, emit series, and start streaming."""
        self._symbol = params.symbol
        interval = params.interval
        series_id = params.series_id

        # Validate that we can map this interval
        upstox = tv_resolution_to_upstox(interval)
        if upstox is None:
            await self.realtime.send_error(f"Unsupported interval: {interval!r}")
            return

        try:
            from_date: date | None = None
            to_date: date | None = None
            if params.from_date:
                from_date = date.fromisoformat(params.from_date)
            if params.to_date:
                to_date = date.fromisoformat(params.to_date)

            candles = await self.candle_manager.get_candles(
                params.symbol,
                interval,
                from_date,
                to_date,
            )
            logger.info(
                "Fetched %d candles for %s %s", len(candles), params.symbol, interval
            )

            # Emit chart_series
            data = []
            unit, _ = upstox
            for c in candles:
                ts_ms = self._parse_timestamp(c.timestamp, unit)
                data.append(
                    ChartCandleData(
                        time=ts_ms,
                        open=c.open,
                        high=c.high,
                        low=c.low,
                        close=c.close,
                        volume=c.volume,
                    )
                )

            await self.realtime.send(
                ChartSeriesResponse(
                    p=(
                        self.session_id,
                        params.symbol,
                        interval,
                        data,
                        series_id,
                        len(data) == 0,
                    )
                )
            )
            logger.info(
                "Sent chart_series for %s with %d bars. series_id=%s",
                params.symbol,
                len(data),
                series_id,
            )

        except Exception as e:
            logger.exception("Error loading chart for %s: %s", params.symbol, e)
            await self.realtime.send_error(f"Error loading chart: {str(e)}")

    def _parse_timestamp(self, ts_val: Any, unit: str) -> int:
        """Parse Upstox timestamp (ISO string or epoch ms) based on chart unit.

        - D/W/M: Force digits to UTC midnight (09:15 IST -> 09:15 UTC -> 00:00 UTC).
        - Intraday: Authentic UTC conversion (09:15 IST -> 03:45 UTC).
        """
        if isinstance(ts_val, (int, float)):
            # If it's a Daily candle epoch (IST midnight), it will be 18:30 UTC previous day.
            # We shift it by +5.5 hours to recover the IST wall-clock and zero the time.
            if unit in ("days", "weeks", "months"):
                shifted = int(ts_val) + 19800000
                dt = datetime.fromtimestamp(shifted / 1000, tz=timezone.utc)
                return int(
                    dt.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
                    * 1000
                )
            return int(ts_val)

        # Parse IST ISO string
        dt = datetime.fromisoformat(ts_val)
        if unit in ("days", "weeks", "months"):
            # Force wall-clock digits to UTC midnight
            return int(dt.replace(tzinfo=timezone.utc).timestamp() * 1000)

        # Authentic UTC conversion
        return int(dt.timestamp() * 1000)

    async def _start_streaming(
        self, ticker: str, interval: str, series_id: str | None = None
    ) -> None:
        """Start a background task to stream real-time candle updates."""
        # If no series_id, we treat this as the "legacy" single-stream chart session
        sid = series_id or "default"
        self._stop_streaming(sid)
        self._streaming_tasks[sid] = asyncio.create_task(
            self._stream_loop(ticker, interval, series_id)
        )

    async def _stream_loop(
        self, ticker: str, interval: str, series_id: str | None = None
    ) -> None:
        """Subscribe to manager and push updates over WebSocket.

        For 1min and 1D intervals, uses raw feed directly.
        For other intervals, uses the CandleAggregator for real-time aggregation.
        """
        # Determine if this interval needs aggregation
        _passthrough_intervals = {"1m", "1", "1d", "1D", "D"}
        needs_aggregation = interval not in _passthrough_intervals

        upstox = tv_resolution_to_upstox(interval)
        unit = upstox[0] if upstox else "minutes"

        try:
            await self.candle_manager.subscribe(ticker)

            if needs_aggregation:
                # Use aggregator for higher timeframes
                sub = self.candle_manager.subscribe_aggregated(ticker, interval)
                try:
                    while True:
                        try:
                            update = await asyncio.wait_for(sub.queue.get(), timeout=1.0)
                        except asyncio.TimeoutError:
                            continue

                        ts_ms = self._parse_timestamp(update["timestamp"], unit)

                        candle = ChartCandleData(
                            time=ts_ms,
                            open=update["open"],
                            high=update["high"],
                            low=update["low"],
                            close=update["close"],
                            volume=update["volume"],
                        )

                        await self.realtime.send(
                            ChartUpdateResponse(
                                p=(self.session_id, ticker, candle, series_id)
                            )
                        )
                finally:
                    self.candle_manager.unsubscribe_aggregated(ticker, interval)
            else:
                # Direct passthrough for 1min and 1D
                async for update in self.candle_manager.on_candle_update():
                    if update["ticker"] != ticker or update["interval"] != interval:
                        continue

                    ts_ms = self._parse_timestamp(update["timestamp"], unit)

                    candle = ChartCandleData(
                        time=ts_ms,
                        open=update["open"],
                        high=update["high"],
                        low=update["low"],
                        close=update["close"],
                        volume=update["volume"],
                    )

                    await self.realtime.send(
                        ChartUpdateResponse(
                            p=(self.session_id, ticker, candle, series_id)
                        )
                    )

        except asyncio.CancelledError:
            await self.candle_manager.unsubscribe(ticker)
        except Exception:
            logger.exception("Unexpected error in chart stream loop")

    def _stop_streaming(self, series_id: str = "default") -> None:
        """Stop a specific background streaming task."""
        task = self._streaming_tasks.pop(series_id, None)
        if task:
            task.cancel()

    def stop(self) -> None:
        """Stop everything."""
        for task in self._streaming_tasks.values():
            task.cancel()
        self._streaming_tasks.clear()

    def __repr__(self) -> str:
        return f"ChartSession(id={self.session_id}, symbol={self._symbol})"
