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

        # Cached parsed ASTs (built once at _start)
        self._parsed_columns: list[tuple[ColumnDef, object | None]] = []
        self._parsed_conditions: dict[str, list[tuple[dict, object | None]]] = {}

        # Change detection — last emitted values
        self._last_values: dict[str, list[Any]] = {}  # col_id → values (full snapshot)

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

        # Pre-parse formula ASTs and cache condition sets
        self._cache_formulas()

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
    # Data loading (DB) + Formula caching
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
            "Screener %s: loading data for user=%s, source=%s",
            self.session_id,
            user_id,
            self.params.source,
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

            # Load columns directly from params
            self._columns = self.params.columns or []
            logger.info(
                "Screener %s: loaded %d columns",
                self.session_id,
                len(self._columns),
            )

    def _cache_formulas(self) -> None:
        """Pre-parse all formula ASTs and inline condition formulas at start time."""
        # Parse value column formulas
        self._parsed_columns = []
        for col in self._columns:
            if col.type == "value" and col.value_formula:
                try:
                    ast = parse(col.value_formula)
                    self._parsed_columns.append((col, ast))
                except FormulaError as e:
                    logger.warning("Column formula parse error: %s", e.message)
                    self._parsed_columns.append((col, None))
            else:
                self._parsed_columns.append((col, None))

        # Parse inline condition formulas (keyed by column id)
        self._parsed_conditions = {}

        condition_columns = [
            col for col in self._columns if col.type == "condition" and col.conditions
        ]

        for col in condition_columns:
            parsed = []
            for cond in col.conditions or []:
                formula = (
                    cond.get("formula", "") if isinstance(cond, dict) else cond.formula
                )
                try:
                    ast = parse(formula)
                    parsed.append((cond, ast))
                except FormulaError, Exception:
                    parsed.append((cond, None))
            self._parsed_conditions[col.id] = parsed

    # ------------------------------------------------------------------
    # Filter evaluation
    # ------------------------------------------------------------------

    async def _run_filter(self) -> bool:
        """Evaluate conditions and emit screener_filter if the set changed.

        Returns True if the visible ticker set changed.
        """
        if not self.params.filter_active:
            # No filtering — all symbols are visible
            new_tickers = list(self._symbols)
        else:
            new_tickers = self._evaluate_filter()

        # Only emit if the set has changed
        if new_tickers != self._visible_tickers:
            self._visible_tickers = new_tickers
            self._last_values.clear()  # reset value cache on filter change
            rows = [ScreenerFilterRow(ticker=t) for t in self._visible_tickers]
            await self.realtime.send(ScreenerFilterResponse(p=(self.session_id, rows)))
            return True
        return False

    def _evaluate_filter(self) -> list[str]:
        """Apply column condition filters using inline conditions."""
        manager = self.realtime.manager

        active_filter_columns = [
            col
            for col in self._columns
            if col.type == "condition" and col.filter == "active"
        ]

        if not active_filter_columns:
            return list(self._symbols)

        passing_tickers = []
        for symbol in self._symbols:
            passes = True
            for col in active_filter_columns:
                if not col.conditions:
                    continue

                tf = col.conditions_tf or "D"
                df = manager.get_ohlcv(symbol, timeframe=tf)
                if df is None or len(df) == 0:
                    continue

                logic = col.conditions_logic or "and"
                condition_results = self._eval_conditions(col.id, df, logic)
                if not condition_results:
                    passes = False
                    break

            if passes:
                passing_tickers.append(symbol)

        return passing_tickers

    def _eval_conditions(
        self,
        col_id: str,
        df: pd.DataFrame,
        logic: str,
    ) -> bool:
        """Evaluate inline conditions for a column using pre-parsed ASTs."""
        parsed = self._parsed_conditions.get(col_id, [])
        if not parsed:
            return True

        results = []
        for cond, ast in parsed:
            if ast is None:
                results.append(False)
                continue
            try:
                result = evaluate(ast, df)
                if result.dtype == bool:
                    met = bool(result[-1]) if len(result) > 0 else False
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
        """Evaluate all column formulas for visible tickers and emit only changed columns."""
        if not self._visible_tickers or not self._columns:
            return

        values_map = self._evaluate_columns()
        if not values_map:
            return

        # Diff against last emitted — only send columns whose values changed
        changed: dict[str, list[Any]] = {}
        for col_id, values in values_map.items():
            if self._last_values.get(col_id) != values:
                changed[col_id] = values

        if changed:
            self._last_values.update(changed)
            await self.realtime.send(
                ScreenerValuesResponse(p=(self.session_id, changed))
            )

    def _evaluate_columns(self) -> dict[str, list[Any]]:
        """Compute column values for all visible tickers using cached ASTs."""
        manager = self.realtime.manager
        values_map: dict[str, list[Any]] = {}

        for col, col_ast in self._parsed_columns:
            if col.type != "value" or col_ast is None:
                continue

            col_values = []
            for symbol in self._visible_tickers:
                tf = col.value_formula_tf or "D"
                df = manager.get_ohlcv(symbol, timeframe=tf)
                if df is None or len(df) == 0:
                    col_values.append(None)
                    continue

                try:
                    res = evaluate(col_ast, df)
                    res = np.asarray(res)

                    bar_ago = col.value_formula_x_bar_ago or 0
                    if bar_ago:
                        idx = -(bar_ago + 1)
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
                changed = await self._run_filter()
                if changed:
                    # Only recompute values if the filter set actually changed
                    await self._run_values()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error("Filter loop error in %s: %s", self.session_id, e)

    async def _values_loop(self) -> None:
        """Stream column values in realtime.

        Subscribes to per-symbol updates, collects which symbols changed,
        then after a 1s debounce window re-evaluates columns only for those
        symbols and sends a ``screener_values`` diff.
        """
        dirty_symbols: set[str] = set()
        debounce_task: asyncio.Task | None = None

        async def flush() -> None:
            """Wait 1s, then evaluate only the dirty symbols and emit changes."""
            nonlocal dirty_symbols
            await asyncio.sleep(1.0)

            if not dirty_symbols or not self._visible_tickers:
                dirty_symbols.clear()
                return

            # Take the current dirty set and clear it
            symbols_to_eval = dirty_symbols & set(self._visible_tickers)
            dirty_symbols.clear()

            if not symbols_to_eval:
                return

            # Evaluate columns only for changed symbols
            partial = self._evaluate_columns_for_symbols(list(symbols_to_eval))

            # Merge partial results into the full last-emitted snapshot
            # and detect which columns actually changed
            changed: dict[str, list[Any]] = {}
            for col_id, sym_values in partial.items():
                current = list(self._last_values.get(col_id, []))
                # Ensure array is the right length
                while len(current) < len(self._visible_tickers):
                    current.append(None)

                for sym, val in sym_values.items():
                    try:
                        idx = self._visible_tickers.index(sym)
                        current[idx] = val
                    except ValueError:
                        continue

                if self._last_values.get(col_id) != current:
                    changed[col_id] = current
                    self._last_values[col_id] = current

            if changed:
                await self.realtime.send(
                    ScreenerValuesResponse(p=(self.session_id, changed))
                )

        try:
            async for update in self.realtime.manager.subscribe():
                symbol = update["symbol"]
                if self._visible_tickers and symbol in self._visible_tickers:
                    dirty_symbols.add(symbol)
                    # Start/restart the debounce timer
                    if debounce_task is None or debounce_task.done():
                        debounce_task = asyncio.create_task(flush())
        except asyncio.CancelledError:
            if debounce_task and not debounce_task.done():
                debounce_task.cancel()
        except Exception as e:
            logger.error("Values loop error in %s: %s", self.session_id, e)

    def _evaluate_columns_for_symbols(
        self, symbols: list[str]
    ) -> dict[str, dict[str, Any]]:
        """Evaluate columns only for the given symbols.

        Returns ``{col_id: {symbol: value}}`` — a sparse map of results.
        """
        manager = self.realtime.manager
        result: dict[str, dict[str, Any]] = {}

        for col, col_ast in self._parsed_columns:
            if col.type != "value" or col_ast is None:
                continue

            col_result: dict[str, Any] = {}
            for symbol in symbols:
                tf = col.value_formula_tf or "D"
                df = manager.get_ohlcv(symbol, timeframe=tf)
                if df is None or len(df) == 0:
                    col_result[symbol] = None
                    continue

                try:
                    res = evaluate(col_ast, df)
                    res = np.asarray(res)

                    bar_ago = col.value_formula_x_bar_ago or 0
                    if bar_ago:
                        idx = -(bar_ago + 1)
                        val = res[idx] if len(res) >= abs(idx) else None
                    else:
                        val = res[-1] if len(res) > 0 else None

                    if val is not None:
                        if isinstance(val, (np.integer, np.floating)):
                            val = val.item()
                        elif isinstance(val, np.bool_):
                            val = bool(val)

                    col_result[symbol] = val
                except (FormulaError, Exception) as e:
                    logger.warning(
                        "Column %s eval failed for %s: %s", col.id, symbol, e
                    )
                    col_result[symbol] = None

            result[col.id] = col_result

        return result

    def __repr__(self) -> str:
        return f"ScreenerSession(id={self.session_id!r})"
