"""ScreenerSession — per-screener state within a RealtimeSession."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from .session import RealtimeSession

from terminal.column.models import ColumnDef
from terminal.column import service as column_service
from terminal.condition import service as condition_service
from terminal.lists import service as lists_service
from terminal.database.core import engine
from terminal.formula import FormulaError, evaluate, parse
from sqlalchemy.orm import Session

from .models import (
    CreateScreenerRequest,
    ModifyScreenerRequest,
    ScreenerFilterResponse,
    ScreenerFilterRow,
    ScreenerParams,
    ScreenerRequest,
    ScreenerValuesResponse,
)

logger = logging.getLogger(__name__)

# Minimum filter re-evaluation interval in seconds
_MIN_FILTER_INTERVAL = 5


class ScreenerSession:
    """
    Holds state for a single screener subscription.

    Created via ``create_screener`` and stored inside the
    parent :class:`RealtimeSession`.  All screener-related messages
    (after creation) are forwarded here via :meth:`handle`.
    """

    def __init__(
        self,
        session_id: str,
        *,
        realtime: "RealtimeSession",
    ) -> None:
        self.session_id = session_id
        self.realtime = realtime
        self.params = ScreenerParams()

        # Runtime state
        self._symbols: list[str] = []
        self._columns: list[ColumnDef] = []
        self._visible_tickers: list[str] | None = None  # None = never emitted

        # Background tasks
        self._filter_task: asyncio.Task | None = None
        self._values_task: asyncio.Task | None = None

    # ------------------------------------------------------------------
    # Message dispatch
    # ------------------------------------------------------------------

    async def handle(self, msg: ScreenerRequest) -> None:
        """Handle a screener request forwarded from the RealtimeSession."""
        match msg.m:
            case "create_screener":
                await self._handle_create_screener(msg)  # type: ignore[arg-type]
            case "modify_screener":
                await self._handle_modify_screener(msg)  # type: ignore[arg-type]
            case _:
                logger.warning("Unhandled screener message: %s", msg.m)

    async def _handle_create_screener(self, msg: CreateScreenerRequest) -> None:
        """Handle a create_screener request (initialization)."""
        _, params = msg.p
        if params is not None:
            self.params = params
        await self._start()

    async def _handle_modify_screener(self, msg: ModifyScreenerRequest) -> None:
        """Handle a modify_screener request."""
        _, params = msg.p
        self.stop()
        self.params = params
        await self._start()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def _start(self) -> None:
        """Load data, run initial evaluation, and start background loops."""
        try:
            self._load_data()
        except Exception:
            logger.exception("Failed to load data for screener %s", self.session_id)
            return

        logger.info(
            "Screener %s loaded %d symbols, %d columns",
            self.session_id,
            len(self._symbols),
            len(self._columns),
        )

        if not self._symbols:
            logger.warning("Screener %s: no symbols loaded, skipping", self.session_id)
            return

        # Initial evaluation
        try:
            await self._run_filter()
            await self._run_values()
        except Exception:
            logger.exception(
                "Initial evaluation failed for screener %s", self.session_id
            )
            return

        # Start background loops
        if self.params.filter_active:
            interval = max(_MIN_FILTER_INTERVAL, self.params.filter_interval)
            self._filter_task = asyncio.create_task(self._filter_loop(interval))

        self._values_task = asyncio.create_task(self._values_loop())

    def stop(self) -> None:
        """Cancel background tasks."""
        if self._filter_task:
            self._filter_task.cancel()
            self._filter_task = None
        if self._values_task:
            self._values_task.cancel()
            self._values_task = None

    # ------------------------------------------------------------------
    # Data loading (DB)
    # ------------------------------------------------------------------

    def _load_data(self) -> None:
        """Load list symbols and column definitions from the database."""
        self._symbols = []
        self._columns = []

        if not self.params.source:
            logger.warning("Screener %s: no source list ID", self.session_id)
            return

        user_id = self.realtime.user_id
        logger.info(
            "Screener %s: loading data for user=%s, source=%s, column_set=%s",
            self.session_id,
            user_id,
            self.params.source,
            self.params.column_set_id,
        )

        with Session(engine) as session:
            # Load list and its symbols
            lst = lists_service.get(session, self.params.source, user_id=user_id)
            if not lst:
                logger.warning(
                    "Screener %s: list %s not found for user %s",
                    self.session_id,
                    self.params.source,
                    user_id,
                )
                return

            self._symbols = lists_service.get_symbols(session, lst, user_id=user_id)
            logger.info(
                "Screener %s: loaded %d symbols", self.session_id, len(self._symbols)
            )

            # Load column set
            if self.params.column_set_id:
                cs = column_service.get(session, user_id, self.params.column_set_id)
                if cs and cs.columns:
                    self._columns = [
                        ColumnDef(**c) if isinstance(c, dict) else c for c in cs.columns
                    ]
                    logger.info(
                        "Screener %s: loaded %d columns",
                        self.session_id,
                        len(self._columns),
                    )
                else:
                    logger.warning(
                        "Screener %s: column set %s not found or empty",
                        self.session_id,
                        self.params.column_set_id,
                    )

    # ------------------------------------------------------------------
    # Filter evaluation
    # ------------------------------------------------------------------

    async def _run_filter(self) -> None:
        """Evaluate conditions and emit screener_filter if the set changed."""
        if not self.params.filter_active:
            # No filtering — all symbols are visible
            new_tickers = list(self._symbols)
        else:
            new_tickers = self._evaluate_filter()

        # Only emit if the set has changed
        if new_tickers != self._visible_tickers:
            self._visible_tickers = new_tickers
            rows = [ScreenerFilterRow(ticker=t) for t in self._visible_tickers]
            await self.realtime.send(ScreenerFilterResponse(p=(self.session_id, rows)))

    def _evaluate_filter(self) -> list[str]:
        """Apply column condition filters to determine visible tickers."""
        manager = self.realtime.manager

        # Find columns that need condition evaluation
        filter_columns = [
            col for col in self._columns if col.filter in ("active", "inactive")
        ]

        if not filter_columns:
            # No filter columns → all symbols pass
            return list(self._symbols)

        # Load condition sets for filter columns
        condition_sets: dict[str, Any] = {}
        with Session(engine) as session:
            for col in filter_columns:
                if col.condition_id and col.condition_id not in condition_sets:
                    cs = condition_service.get(
                        session, self.realtime.user_id, col.condition_id
                    )
                    if cs:
                        condition_sets[col.condition_id] = cs

        # Only columns with filter="active" actually filter; "inactive" just generates values
        active_filter_columns = [c for c in filter_columns if c.filter == "active"]

        passing_tickers = []
        for symbol in self._symbols:
            passes = True
            for col in active_filter_columns:
                if not col.condition_id:
                    continue
                cs = condition_sets.get(col.condition_id)
                if not cs or not cs.conditions:
                    continue

                tf = col.timeframe or "D"
                df = manager.get_ohlcv(symbol, timeframe=tf)
                if df is None or len(df) == 0:
                    # No OHLCV data yet — skip this condition (pass through)
                    continue

                condition_results = self._eval_conditions(
                    df, cs.conditions, cs.conditional_logic
                )
                if not condition_results:
                    passes = False
                    break

            if passes:
                passing_tickers.append(symbol)

        return passing_tickers

    @staticmethod
    def _eval_conditions(
        df: pd.DataFrame,
        conditions: list[dict],
        logic: str,
    ) -> bool:
        """Evaluate a list of conditions against a DataFrame."""
        results = []
        for cond in conditions:
            formula = (
                cond.get("formula", "") if isinstance(cond, dict) else cond.formula
            )
            try:
                ast = parse(formula)
                result = evaluate(ast, df)
                if result.dtype == bool:
                    met = bool(result.iloc[-1]) if len(result) > 0 else False
                else:
                    met = False
            except FormulaError, Exception:
                met = False
            results.append(met)

        if not results:
            return True

        if logic == "or":
            return any(results)
        return all(results)  # default "and"

    # ------------------------------------------------------------------
    # Column value evaluation
    # ------------------------------------------------------------------

    async def _run_values(self) -> None:
        """Evaluate all column formulas for visible tickers and emit."""
        if not self._visible_tickers or not self._columns:
            return

        values_map = self._evaluate_columns()
        if values_map:
            await self.realtime.send(
                ScreenerValuesResponse(p=(self.session_id, values_map))
            )

    def _evaluate_columns(self) -> dict[str, list[Any]]:
        """Compute column values for all visible tickers."""
        manager = self.realtime.manager
        values_map: dict[str, list[Any]] = {}

        for col in self._columns:
            if col.type != "value" or not col.formula:
                continue

            col_values = []
            for symbol in self._visible_tickers:
                tf = col.timeframe or "D"
                df = manager.get_ohlcv(symbol, timeframe=tf)
                if df is None or len(df) == 0:
                    col_values.append(None)
                    continue

                try:
                    ast = parse(col.formula)
                    res = evaluate(ast, df)
                    res = np.asarray(res)

                    if col.bar_ago:
                        idx = -(col.bar_ago + 1)
                        val = res[idx] if len(res) >= abs(idx) else None
                    else:
                        val = res[-1] if len(res) > 0 else None

                    # Convert numpy types to native Python
                    if val is not None:
                        if isinstance(val, (np.integer, np.floating)):
                            val = val.item()
                        elif isinstance(val, np.bool_):
                            val = bool(val)

                    col_values.append(val)
                except (FormulaError, Exception) as e:
                    logger.warning(
                        "Column %s eval failed for %s: %s", col.id, symbol, e
                    )
                    col_values.append(None)

            values_map[col.id] = col_values

        return values_map

    # ------------------------------------------------------------------
    # Background loops
    # ------------------------------------------------------------------

    async def _filter_loop(self, interval: int) -> None:
        """Periodically re-evaluate the filter."""
        try:
            while True:
                await asyncio.sleep(interval)
                await self._run_filter()
                # Re-evaluate values after filter change
                await self._run_values()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error("Filter loop error in %s: %s", self.session_id, e)

    async def _values_loop(self) -> None:
        """Stream column values in realtime via MarketDataManager updates."""
        try:
            async for update in self.realtime.manager.subscribe():
                symbol = update["symbol"]
                if symbol in self._visible_tickers:
                    # A symbol we're watching got a candle update — recalculate values
                    await self._run_values()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error("Values loop error in %s: %s", self.session_id, e)

    def __repr__(self) -> str:
        return f"ScreenerSession(id={self.session_id!r})"
