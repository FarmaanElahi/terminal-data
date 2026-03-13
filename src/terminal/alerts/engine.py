"""AlertEngine — background alert evaluation driven by MarketDataManager updates.

Subscribes to ``MarketDataManager.subscribe()`` and evaluates all active
alerts whenever their symbol's data changes.  Uses an in-memory index
grouped by symbol so all alerts for a symbol share a single OHLCV lookup.

Log inserts are batched via an async queue and flushed periodically.
Notifications are dispatched asynchronously to avoid blocking the
evaluation loop.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

import numpy as np

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from terminal.alerts.drawing import evaluate_drawing_condition
from terminal.alerts.models import Alert, AlertLog
from terminal.formula import FormulaError, evaluate, parse

if TYPE_CHECKING:
    from terminal.market_feed.manager import MarketDataManager

logger = logging.getLogger(__name__)

# Debounce window — collect dirty symbols for this long before evaluating
_DEBOUNCE_SECONDS = 1.0

# Log flush interval — batch-insert alert logs every N seconds
_LOG_FLUSH_INTERVAL = 5.0


class _CachedAlert:
    """In-memory representation of an active alert with pre-parsed ASTs."""

    __slots__ = (
        "id", "user_id", "symbol", "alert_type", "status",
        "trigger_condition", "guard_conditions",
        "frequency", "frequency_interval",
        "trigger_count", "last_triggered_at",
        "notification_channels", "drawing_id", "name", "alert_sound",
        "_trigger_ast", "_guard_asts",
    )

    def __init__(self, alert: Alert) -> None:
        self.id = alert.id
        self.user_id = alert.user_id
        self.symbol = alert.symbol
        self.alert_type = alert.alert_type
        self.status = alert.status
        self.trigger_condition = alert.trigger_condition
        self.guard_conditions = alert.guard_conditions or []
        self.frequency = alert.frequency
        self.frequency_interval = alert.frequency_interval
        self.trigger_count = alert.trigger_count
        self.last_triggered_at = alert.last_triggered_at
        self.notification_channels = alert.notification_channels
        self.drawing_id = alert.drawing_id
        self.name = alert.name
        self.alert_sound = alert.alert_sound

        # Pre-parse formula ASTs
        self._trigger_ast: object | None = None
        self._guard_asts: list[object | None] = []

        self._parse_formulas()

    def _parse_formulas(self) -> None:
        """Pre-parse formula ASTs for fast evaluation."""
        # Trigger condition
        if self.alert_type == "formula":
            formula = self.trigger_condition.get("formula", "")
            if formula:
                try:
                    self._trigger_ast = parse(formula)
                except (FormulaError, Exception) as e:
                    logger.warning(
                        "Alert %s: failed to parse trigger formula '%s': %s",
                        self.id, formula, e,
                    )

        # Guard conditions
        for guard in self.guard_conditions:
            formula = guard.get("formula", "") if isinstance(guard, dict) else ""
            if formula:
                try:
                    self._guard_asts.append(parse(formula))
                except (FormulaError, Exception) as e:
                    logger.warning(
                        "Alert %s: failed to parse guard formula '%s': %s",
                        self.id, formula, e,
                    )
                    self._guard_asts.append(None)
            else:
                self._guard_asts.append(None)

    def is_cooldown_expired(self) -> bool:
        """Check if enough time has passed since the last trigger."""
        if self.last_triggered_at is None:
            return True

        now = datetime.now(timezone.utc)
        elapsed = (now - self.last_triggered_at).total_seconds()

        if self.frequency == "once":
            return self.trigger_count == 0
        elif self.frequency == "once_per_minute":
            return elapsed >= max(60, self.frequency_interval)
        elif self.frequency == "once_per_bar":
            # For daily bars, one trigger per bar (~24h minimum)
            return elapsed >= 86400
        elif self.frequency == "end_of_day":
            # Only trigger near market close (15:30 IST → 10:00 UTC)
            return elapsed >= 86400
        else:
            return elapsed >= self.frequency_interval


class AlertEngine:
    """Background alert evaluation engine.

    Usage::

        engine = AlertEngine(market_manager)
        await engine.start()   # loads alerts + starts eval loop
        ...
        await engine.stop()
    """

    def __init__(self, market_manager: "MarketDataManager", session_factory: async_sessionmaker) -> None:
        self.manager = market_manager
        self._session_factory = session_factory

        # In-memory index: symbol → list of CachedAlert
        self._index: dict[str, list[_CachedAlert]] = {}

        # Alert ID → CachedAlert for fast lookups
        self._alerts_by_id: dict[str, _CachedAlert] = {}

        # Background tasks
        self._eval_task: asyncio.Task | None = None
        self._flush_task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()

        # Log queue for batched DB writes
        self._log_queue: asyncio.Queue[dict] = asyncio.Queue()

        # Connected WebSocket sessions for in-app push
        self._sessions: list[Any] = []  # list[RealtimeSession]

        # Notification dispatcher (set externally after init)
        self._dispatcher: Any | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Load all active alerts from DB and start the evaluation loop."""
        await self._load_alerts_from_db()
        total = sum(len(v) for v in self._index.values())
        logger.info(
            "AlertEngine started: %d active alerts across %d symbols",
            total, len(self._index),
        )

        self._stop_event.clear()
        self._eval_task = asyncio.create_task(self._evaluation_loop())
        self._flush_task = asyncio.create_task(self._log_flush_loop())

    async def stop(self) -> None:
        """Stop the evaluation loop and flush remaining logs."""
        self._stop_event.set()
        if self._eval_task:
            self._eval_task.cancel()
            try:
                await self._eval_task
            except asyncio.CancelledError:
                pass
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
        # Final flush
        await self._flush_logs()
        logger.info("AlertEngine stopped.")

    def set_dispatcher(self, dispatcher: Any) -> None:
        """Set the notification dispatcher (called from main.py)."""
        self._dispatcher = dispatcher

    # ------------------------------------------------------------------
    # Session management (for in-app push)
    # ------------------------------------------------------------------

    def register_session(self, session: Any) -> None:
        """Register a WebSocket session for in-app alert push."""
        if session not in self._sessions:
            self._sessions.append(session)

    def unregister_session(self, session: Any) -> None:
        """Unregister a WebSocket session."""
        try:
            self._sessions.remove(session)
        except ValueError:
            pass

    # ------------------------------------------------------------------
    # Alert index management
    # ------------------------------------------------------------------

    async def _load_alerts_from_db(self) -> None:
        """Load all active alerts from the database into the in-memory index."""
        self._index.clear()
        self._alerts_by_id.clear()

        async with self._session_factory() as session:
            from terminal.alerts.service import get_active_alerts_by_symbol
            raw_index = await get_active_alerts_by_symbol(session)

        for symbol, alerts in raw_index.items():
            cached = []
            for alert in alerts:
                ca = _CachedAlert(alert)
                cached.append(ca)
                self._alerts_by_id[ca.id] = ca
            self._index[symbol] = cached

    def add_alert(self, alert: Alert) -> None:
        """Add a new alert to the in-memory index (called on create)."""
        ca = _CachedAlert(alert)
        self._index.setdefault(alert.symbol, []).append(ca)
        self._alerts_by_id[ca.id] = ca

    def remove_alert(self, alert_id: str) -> None:
        """Remove an alert from the in-memory index (called on delete)."""
        ca = self._alerts_by_id.pop(alert_id, None)
        if ca and ca.symbol in self._index:
            self._index[ca.symbol] = [
                a for a in self._index[ca.symbol] if a.id != alert_id
            ]
            if not self._index[ca.symbol]:
                del self._index[ca.symbol]

    def update_alert(self, alert: Alert) -> None:
        """Update an alert in the index (called on update/status change)."""
        self.remove_alert(alert.id)
        if alert.status == "active":
            self.add_alert(alert)

    def remove_alerts_by_drawing(self, drawing_id: str) -> list[str]:
        """Remove all alerts linked to a drawing. Returns removed alert IDs."""
        removed = []
        for alert_id, ca in list(self._alerts_by_id.items()):
            if ca.drawing_id == drawing_id:
                self.remove_alert(alert_id)
                removed.append(alert_id)
        return removed

    # ------------------------------------------------------------------
    # Main evaluation loop
    # ------------------------------------------------------------------

    async def _evaluation_loop(self) -> None:
        """Subscribe to market data updates and evaluate alerts."""
        dirty_symbols: set[str] = set()
        debounce_task: asyncio.Task | None = None

        async def flush() -> None:
            """Wait for debounce window, then evaluate dirty symbols."""
            nonlocal dirty_symbols
            await asyncio.sleep(_DEBOUNCE_SECONDS)

            if not dirty_symbols:
                return

            symbols_to_eval = set(dirty_symbols)
            dirty_symbols.clear()

            for symbol in symbols_to_eval:
                if self._stop_event.is_set():
                    break
                alerts = self._index.get(symbol, [])
                if not alerts:
                    continue
                try:
                    await self._evaluate_symbol(symbol, alerts)
                except Exception as e:
                    logger.error(
                        "AlertEngine: error evaluating symbol %s: %s",
                        symbol, e, exc_info=True,
                    )

        try:
            async for update in self.manager.subscribe():
                if self._stop_event.is_set():
                    break

                symbol = update["symbol"]
                if symbol in self._index:
                    dirty_symbols.add(symbol)
                    if debounce_task is None or debounce_task.done():
                        debounce_task = asyncio.create_task(flush())

        except asyncio.CancelledError:
            if debounce_task and not debounce_task.done():
                debounce_task.cancel()
        except Exception as e:
            logger.error("AlertEngine evaluation loop crashed: %s", e, exc_info=True)

    async def _evaluate_symbol(
        self, symbol: str, alerts: list[_CachedAlert]
    ) -> None:
        """Evaluate all alerts for a single symbol."""
        # Get the shared OHLCV DataFrame (one lookup per symbol)
        df = self.manager.get_ohlcv(symbol, timeframe="D")
        if df is None or len(df) == 0:
            return

        current_close = float(df["close"].iloc[-1])
        previous_close = float(df["close"].iloc[-2]) if len(df) > 1 else current_close
        current_timestamp = int(df.index[-1])

        for ca in alerts:
            if ca.status != "active":
                continue
            if not ca.is_cooldown_expired():
                continue

            try:
                triggered = self._evaluate_single(
                    ca, df, current_close, previous_close, current_timestamp
                )
            except Exception as e:
                logger.warning(
                    "Alert %s eval error: %s", ca.id, e
                )
                continue

            if triggered:
                await self._fire_alert(ca, current_close, symbol)

    def _evaluate_single(
        self,
        ca: _CachedAlert,
        df: Any,
        current_close: float,
        previous_close: float,
        current_timestamp: int,
    ) -> bool:
        """Evaluate a single alert's trigger + guard conditions."""
        # 1. Evaluate primary trigger
        trigger_met = False

        if ca.alert_type == "formula":
            if ca._trigger_ast is not None:
                try:
                    result = evaluate(ca._trigger_ast, df)
                    result = np.asarray(result)
                    if result.dtype == bool:
                        trigger_met = bool(result[-1]) if len(result) > 0 else False
                    else:
                        # Non-boolean result — treat non-zero last value as True
                        trigger_met = bool(result[-1]) if len(result) > 0 else False
                except (FormulaError, Exception) as e:
                    logger.debug("Alert %s formula eval error: %s", ca.id, e)
                    return False
        elif ca.alert_type == "drawing":
            trigger_met = evaluate_drawing_condition(
                ca.trigger_condition, current_close, previous_close, current_timestamp
            )

        if not trigger_met:
            return False

        # 2. Evaluate guard conditions (all must be True)
        for guard_ast in ca._guard_asts:
            if guard_ast is None:
                return False  # unparseable guard → fail-safe
            try:
                result = evaluate(guard_ast, df)
                result = np.asarray(result)
                if result.dtype == bool:
                    if not (bool(result[-1]) if len(result) > 0 else False):
                        return False
                else:
                    if not (bool(result[-1]) if len(result) > 0 else False):
                        return False
            except (FormulaError, Exception):
                return False

        return True

    # ------------------------------------------------------------------
    # Alert fire
    # ------------------------------------------------------------------

    async def _fire_alert(
        self, ca: _CachedAlert, trigger_value: float, symbol: str
    ) -> None:
        """Handle a triggered alert: log, notify, update state."""
        # Build message
        if ca.alert_type == "formula":
            formula = ca.trigger_condition.get("formula", "")
            message = f"Alert '{ca.name}' triggered on {symbol}: {formula} (value={trigger_value:.2f})"
        else:
            drawing_type = ca.trigger_condition.get("drawing_type", "drawing")
            trigger_when = ca.trigger_condition.get("trigger_when", "")
            message = f"Alert '{ca.name}' triggered on {symbol}: {drawing_type} {trigger_when} (price={trigger_value:.2f})"

        logger.info("ALERT FIRED: %s", message)

        # Update in-memory state
        ca.trigger_count += 1
        ca.last_triggered_at = datetime.now(timezone.utc)
        if ca.frequency == "once":
            ca.status = "triggered"

        # Queue log entry for batched DB write
        self._log_queue.put_nowait({
            "alert_id": ca.id,
            "user_id": ca.user_id,
            "symbol": symbol,
            "trigger_value": trigger_value,
            "message": message,
        })

        # Persist state change to DB
        asyncio.create_task(self._persist_trigger_state(ca))

        # In-app notification via WebSocket
        await self._push_to_sessions(ca, trigger_value, message)

        # External notifications (Telegram, Web Push)
        if ca.notification_channels and self._dispatcher:
            asyncio.create_task(
                self._dispatch_notifications(ca, trigger_value, message)
            )

    async def _push_to_sessions(
        self, ca: _CachedAlert, trigger_value: float, message: str
    ) -> None:
        """Push alert_triggered to all connected WebSocket sessions for this user."""
        from terminal.realtime.models import AlertTriggeredResponse

        msg = AlertTriggeredResponse(
            p=(
                {
                    "alert_id": ca.id,
                    "alert_name": ca.name,
                    "symbol": ca.symbol,
                    "trigger_value": trigger_value,
                    "message": message,
                    "alert_sound": ca.alert_sound,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            ),
        )

        for session in self._sessions:
            if hasattr(session, "user_id") and session.user_id == ca.user_id:
                try:
                    await session.send(msg)
                except Exception:
                    pass  # WebSocket may be closed

    async def _dispatch_notifications(
        self, ca: _CachedAlert, trigger_value: float, message: str
    ) -> None:
        """Dispatch external notifications."""
        if not self._dispatcher or not ca.notification_channels:
            return
        try:
            await self._dispatcher.dispatch(
                ca.user_id, ca.notification_channels, message,
                alert_name=ca.name,
                symbol=ca.symbol,
                trigger_value=trigger_value,
            )
        except Exception as e:
            logger.error("Failed to dispatch notifications for alert %s: %s", ca.id, e)

    async def _persist_trigger_state(self, ca: _CachedAlert) -> None:
        """Persist alert trigger state to the database."""
        try:
            async with self._session_factory() as session:
                from terminal.alerts.models import Alert as AlertModel
                alert = await session.get(AlertModel, ca.id)
                if alert:
                    alert.trigger_count = ca.trigger_count
                    alert.last_triggered_at = ca.last_triggered_at
                    if ca.frequency == "once":
                        alert.status = "triggered"
                    await session.commit()
        except Exception as e:
            logger.error("Failed to persist trigger state for alert %s: %s", ca.id, e)

    # ------------------------------------------------------------------
    # Log batching
    # ------------------------------------------------------------------

    async def _log_flush_loop(self) -> None:
        """Periodically flush the log queue to the database."""
        try:
            while not self._stop_event.is_set():
                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(), timeout=_LOG_FLUSH_INTERVAL
                    )
                    break
                except asyncio.TimeoutError:
                    pass
                await self._flush_logs()
        except asyncio.CancelledError:
            pass

    async def _flush_logs(self) -> None:
        """Batch-insert all queued alert logs into the database."""
        entries: list[dict] = []
        while not self._log_queue.empty():
            try:
                entries.append(self._log_queue.get_nowait())
            except asyncio.QueueEmpty:
                break

        if not entries:
            return

        try:
            async with self._session_factory() as session:
                for entry in entries:
                    log = AlertLog(
                        alert_id=entry["alert_id"],
                        user_id=entry["user_id"],
                        symbol=entry["symbol"],
                        triggered_at=datetime.now(timezone.utc),
                        trigger_value=entry.get("trigger_value"),
                        message=entry.get("message", ""),
                    )
                    session.add(log)
                await session.commit()
            logger.debug("Flushed %d alert log entries", len(entries))
        except Exception as e:
            logger.error("Failed to flush alert logs: %s", e, exc_info=True)
