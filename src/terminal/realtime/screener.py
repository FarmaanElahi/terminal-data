"""ScreenerSession — per-screener state within a RealtimeSession."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from .session import RealtimeSession

from terminal.column.models import ColumnDef
from terminal.lists import service as lists_service
from terminal.symbols import service as symbols_service
from terminal.database.core import AsyncSessionLocal
from terminal.formula import FormulaError, evaluate, parse
from terminal.config import settings
from terminal.market_feed.provider import _extract_exchange

from .models import (
    CreateScreenerRequest,
    ModifyScreenerRequest,
    ScreenerErrorInfo,
    ScreenerErrorsResponse,
    ScreenerFilterResponse,
    ScreenerFilterRow,
    ScreenerParams,
    ScreenerRequest,
    ScreenerValuesResponse,
)

logger = logging.getLogger(__name__)

# Minimum filter re-evaluation interval in seconds
_MIN_FILTER_INTERVAL = 5

# Maximum symbols evaluated per cycle to prevent CPU starvation
_MAX_SYMBOLS_PER_CYCLE = 5000

# Maximum conditions per screener to prevent abuse
_MAX_CONDITIONS = 50

# Metadata refresh interval (seconds)
_METADATA_REFRESH_INTERVAL = 300  # 5 minutes


class ScreenerCache:
    """Shared cache for screener sessions with identical parameters.

    Multiple sessions viewing the same list+columns reference shared computed
    values instead of each holding a full copy. Ref-counted: evicted when
    the last session unsubscribes.
    """

    _instances: dict[str, "ScreenerCache"] = {}

    @classmethod
    def get_or_create(cls, cache_key: str) -> "ScreenerCache":
        if cache_key not in cls._instances:
            cls._instances[cache_key] = cls(cache_key)
        instance = cls._instances[cache_key]
        instance.ref_count += 1
        return instance

    @classmethod
    def release(cls, cache_key: str) -> None:
        instance = cls._instances.get(cache_key)
        if not instance:
            return
        instance.ref_count -= 1
        if instance.ref_count <= 0:
            del cls._instances[cache_key]
            logger.info("Evicted screener cache: %s", cache_key)

    def __init__(self, cache_key: str) -> None:
        self.cache_key = cache_key
        self.ref_count = 0
        self.values: dict[str, list[Any]] = {}  # col_id -> values


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
        self._metadata: dict[
            str, dict[str, Any]
        ] = {}  # ticker -> metadata (name, logo, etc.)

        # Cached parsed ASTs (built once at _start)
        self._parsed_columns: list[tuple[ColumnDef, object | None]] = []
        self._parsed_conditions: dict[str, list[tuple[dict, object | None]]] = {}

        # Change detection — last emitted values
        self._last_values: dict[str, list[Any]] = {}  # col_id → values (full snapshot)

        # Formula error tracking
        self._formula_errors: list[ScreenerErrorInfo] = []

        # Background tasks
        self._filter_task: asyncio.Task | None = None
        self._values_task: asyncio.Task | None = None
        self._metadata_refresh_task: asyncio.Task | None = None

        # Shared cache
        self._cache_key: str | None = None
        self._shared_cache: ScreenerCache | None = None

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
        t_total = time.perf_counter()

        t0 = time.perf_counter()
        try:
            await self._load_data()
        except Exception:
            logger.exception("Failed to load data for screener %s", self.session_id)
            return
        logger.info(
            "Screener %s [load_data] %.0fms — %d symbols, %d columns",
            self.session_id,
            (time.perf_counter() - t0) * 1000,
            len(self._symbols),
            len(self._columns),
        )

        if not self._symbols:
            logger.warning("Screener %s: no symbols loaded, skipping", self.session_id)
            return

        # Compute shared cache key
        col_ids = sorted(c.id for c in self._columns)
        self._cache_key = f"{self.params.source}:{'|'.join(col_ids)}"
        self._shared_cache = ScreenerCache.get_or_create(self._cache_key)

        t0 = time.perf_counter()
        self._cache_formulas()
        logger.info(
            "Screener %s [cache_formulas] %.0fms",
            self.session_id,
            (time.perf_counter() - t0) * 1000,
        )

        t0 = time.perf_counter()
        try:
            await self._ensure_exchanges_loaded()
        except Exception:
            logger.exception(
                "Failed to load exchange data for screener %s", self.session_id
            )
        logger.info(
            "Screener %s [ensure_exchanges] %.0fms",
            self.session_id,
            (time.perf_counter() - t0) * 1000,
        )

        try:
            t0 = time.perf_counter()
            await self._run_filter(force=True)
            logger.info(
                "Screener %s [initial_eval/run_filter] %.0fms",
                self.session_id,
                (time.perf_counter() - t0) * 1000,
            )
            t0 = time.perf_counter()
            await self._run_values()
            logger.info(
                "Screener %s [initial_eval/run_values] %.0fms",
                self.session_id,
                (time.perf_counter() - t0) * 1000,
            )
        except Exception:
            logger.exception(
                "Initial evaluation failed for screener %s", self.session_id
            )
            return

        logger.info(
            "Screener %s [TOTAL startup] %.0fms",
            self.session_id,
            (time.perf_counter() - t_total) * 1000,
        )

        # Report formula errors to client
        if self._formula_errors:
            await self.realtime.send(
                ScreenerErrorsResponse(p=(self.session_id, self._formula_errors))
            )

        # Start background loops
        if self.params.filter_active:
            interval = max(_MIN_FILTER_INTERVAL, self.params.filter_interval)
            self._filter_task = asyncio.create_task(self._filter_loop(interval))

        self._values_task = asyncio.create_task(self._values_loop())
        self._metadata_refresh_task = asyncio.create_task(self._metadata_refresh_loop())

    def stop(self) -> None:
        """Cancel background tasks and release shared cache."""
        if self._filter_task:
            self._filter_task.cancel()
            self._filter_task = None
        if self._values_task:
            self._values_task.cancel()
            self._values_task = None
        if self._metadata_refresh_task:
            self._metadata_refresh_task.cancel()
            self._metadata_refresh_task = None
        if self._cache_key:
            ScreenerCache.release(self._cache_key)
            self._cache_key = None
            self._shared_cache = None

    # ------------------------------------------------------------------
    # Exchange preloading
    # ------------------------------------------------------------------

    async def _ensure_exchanges_loaded(self) -> None:
        """Pre-load all exchange Parquet files needed by the screener symbols.

        This must be called before any synchronous ``get_ohlcv()`` calls,
        because the provider stores data lazily and ``get_history()``
        returns ``None`` for unloaded exchanges.
        """
        manager = self.realtime.manager
        exchanges_needed: set[str] = set()
        for symbol in self._symbols:
            exchanges_needed.add(_extract_exchange(symbol))

        # Collect all timeframes referenced by columns
        timeframes_needed: set[str] = {"1D"}  # default
        for col in self._columns:
            if col.type == "value" and col.value_formula_tf:
                tf = col.value_formula_tf
                # Map screener timeframe codes (D, W, M) to provider codes (1D, 1W, 1M)
                if tf in ("D", "W", "M"):
                    tf = f"1{tf}"
                timeframes_needed.add(tf)
            if col.type == "condition" and col.conditions_tf:
                tf = col.conditions_tf
                if tf in ("D", "W", "M"):
                    tf = f"1{tf}"
                timeframes_needed.add(tf)

        tasks = []
        for tf in timeframes_needed:
            for ex in exchanges_needed:
                # ensure_loaded() loads from local cache (or remote if first time).
                # The background refresh in MarketDataManager handles freshness.
                tasks.append(manager.provider.ensure_loaded(tf, ex))

        if tasks:
            await asyncio.gather(*tasks)
            logger.info(
                "Screener %s: loaded %d exchanges across %d timeframes",
                self.session_id,
                len(exchanges_needed),
                len(timeframes_needed),
            )

            # Load individual symbol histories into the in-memory store
            # so get_ohlcv() can serve them without round-tripping the provider.
            for symbol in self._symbols:
                for tf in timeframes_needed:
                    history = manager.provider.get_history(symbol, tf)
                    if history is not None and len(history) > 0:
                        manager.store.load_history(symbol, history, tf)

            # Kick off realtime streaming if it wasn't started at boot
            # (happens when exchanges are lazy-loaded after start()).
            await manager.ensure_streaming()

    # ------------------------------------------------------------------
    # Data loading (DB) + Formula caching
    # ------------------------------------------------------------------

    async def _load_data(self) -> None:
        """Load list symbols and column definitions from the database."""
        self._symbols = []
        self._columns = []
        self._section_positions = []

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

        async with AsyncSessionLocal() as session:
            t0 = time.perf_counter()
            lst = await lists_service.get_any_list(
                session, self.params.source, user_id=user_id
            )
            logger.info(
                "Screener %s [load_data/get_list] %.0fms",
                self.session_id,
                (time.perf_counter() - t0) * 1000,
            )
            if not lst:
                logger.warning(
                    "Screener %s: list %s not found for user %s",
                    self.session_id,
                    self.params.source,
                    user_id,
                )
                return

            t0 = time.perf_counter()
            raw_symbols = await lists_service.get_symbols_async(
                session,
                lst,
                user_id=user_id,
                fs=self.realtime.manager.provider.fs,
                settings=settings,
            )
            self._symbols = raw_symbols
            logger.info(
                "Screener %s [load_data/get_symbols] %.0fms — %d symbols",
                self.session_id,
                (time.perf_counter() - t0) * 1000,
                len(self._symbols),
            )

            # Load columns directly from params
            self._columns = self.params.columns or []
            logger.info(
                "Screener %s [load_data/columns] %d columns (from params, no I/O)",
                self.session_id,
                len(self._columns),
            )

            t0 = time.perf_counter()
            self._metadata = await symbols_service.get_metadata_by_tickers(
                self.realtime.manager.provider.fs, settings, self._symbols
            )
            logger.info(
                "Screener %s [load_data/metadata] %.0fms — %d symbols",
                self.session_id,
                (time.perf_counter() - t0) * 1000,
                len(self._metadata),
            )

    def _cache_formulas(self) -> None:
        """Pre-parse all formula ASTs and inline condition formulas at start time."""
        self._formula_errors = []

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
                    self._formula_errors.append(
                        ScreenerErrorInfo(column_id=col.id, message=e.message)
                    )
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
                except (FormulaError, Exception):
                    parsed.append((cond, None))
            self._parsed_conditions[col.id] = parsed

    # ------------------------------------------------------------------
    # Filter evaluation
    # ------------------------------------------------------------------

    async def _run_filter(self, force: bool = False) -> bool:
        """Evaluate conditions and emit screener_filter if the set changed.

        Returns True if the visible ticker set changed.
        """
        t0 = time.perf_counter()
        if not self.params.filter_active:
            # No filtering — all symbols are visible
            new_tickers = list(self._symbols)
        else:
            new_tickers = self._evaluate_filter()
        logger.info(
            "Screener %s [run_filter/evaluate_filter] %.0fms — %d/%d passed",
            self.session_id,
            (time.perf_counter() - t0) * 1000,
            len(new_tickers),
            len(self._symbols),
        )

        # Only emit if the set has changed or force is True
        if force or new_tickers != self._visible_tickers:
            self._visible_tickers = new_tickers
            self._last_values.clear()  # reset value cache on filter change

            # Get initial values for the "full dataframe" response
            t0 = time.perf_counter()
            initial_values = self._evaluate_columns()
            logger.info(
                "Screener %s [run_filter/evaluate_columns] %.0fms — %d cols × %d rows",
                self.session_id,
                (time.perf_counter() - t0) * 1000,
                len(initial_values),
                len(self._visible_tickers),
            )
            self._last_values.update(initial_values)

            rows: list[ScreenerFilterRow] = []
            for t in self._visible_tickers:
                meta = self._metadata.get(t, {})
                # Extract values for this specific row
                row_values = {
                    cid: vals[self._visible_tickers.index(t)]
                    for cid, vals in initial_values.items()
                }
                rows.append(
                    ScreenerFilterRow(
                        ticker=t,
                        name=meta.get("name"),
                        logo=meta.get("logo"),
                        v=row_values,
                    )
                )

            await self.realtime.send(
                ScreenerFilterResponse(p=(self.session_id, rows, len(self._symbols)))
            )
            return True
        return False

    def _evaluate_filter(self) -> list[str]:
        """Apply column condition filters using inline conditions.

        Caps evaluation at _MAX_SYMBOLS_PER_CYCLE to prevent CPU starvation.
        Validates that conditions don't exceed _MAX_CONDITIONS.
        """
        manager = self.realtime.manager

        active_filter_columns = [
            col
            for col in self._columns
            if col.type == "condition" and col.filter == "active"
        ]

        if not active_filter_columns:
            return list(self._symbols)

        # Cap conditions to prevent abuse
        total_conditions = sum(
            len(col.conditions or []) for col in active_filter_columns
        )
        if total_conditions > _MAX_CONDITIONS:
            logger.warning(
                "Screener %s has %d conditions (max %d), truncating",
                self.session_id,
                total_conditions,
                _MAX_CONDITIONS,
            )
            # Only evaluate first N columns
            active_filter_columns = active_filter_columns[:_MAX_CONDITIONS]

        passing_tickers = []
        symbols_to_eval = self._symbols[:_MAX_SYMBOLS_PER_CYCLE]
        if len(self._symbols) > _MAX_SYMBOLS_PER_CYCLE:
            logger.info(
                "Screener %s: throttling evaluation to %d/%d symbols",
                self.session_id,
                _MAX_SYMBOLS_PER_CYCLE,
                len(self._symbols),
            )
        for symbol in symbols_to_eval:
            passes = True
            for col in active_filter_columns:
                if not col.conditions:
                    continue

                tf = col.conditions_tf or "D"
                df = manager.get_ohlcv(symbol, timeframe=tf)
                if df is None or len(df) == 0:
                    passes = False
                    break

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
            except (FormulaError, Exception):
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
            col_values = []
            for symbol in self._visible_tickers:
                if col.type == "value":
                    if col.value_type == "field":
                        # Pull from symbol metadata
                        meta = self._metadata.get(symbol, {})
                        val = meta.get(col.id)
                        col_values.append(val)
                        continue

                    if col_ast is None:
                        col_values.append(None)
                        continue

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
                        # Track runtime error (deduplicated by column_id)
                        if not any(
                            err.column_id == col.id for err in self._formula_errors
                        ):
                            self._formula_errors.append(
                                ScreenerErrorInfo(
                                    column_id=col.id,
                                    message=f"Eval error: {e}",
                                )
                            )

                elif col.type == "condition":
                    tf = col.conditions_tf or "D"
                    df = manager.get_ohlcv(symbol, timeframe=tf)
                    if df is None or len(df) == 0:
                        col_values.append(False)
                        continue

                    logic = col.conditions_logic or "and"
                    val = self._eval_conditions(col.id, df, logic)
                    col_values.append(val)

                else:
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
                try:
                    await self.realtime.send(
                        ScreenerValuesResponse(p=(self.session_id, changed))
                    )
                except (RuntimeError, Exception):
                    # WebSocket may have been closed between debounce start
                    # and flush execution — silently ignore.
                    pass

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
            col_result: dict[str, Any] = {}
            for symbol in symbols:
                if col.type == "value":
                    if col.value_type == "field":
                        # Pull from symbol metadata
                        meta = self._metadata.get(symbol, {})
                        col_result[symbol] = meta.get(col.id)
                        continue

                    if col_ast is None:
                        col_result[symbol] = None
                        continue

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

                elif col.type == "condition":
                    tf = col.conditions_tf or "D"
                    df = manager.get_ohlcv(symbol, timeframe=tf)
                    if df is None or len(df) == 0:
                        col_result[symbol] = False
                        continue

                    logic = col.conditions_logic or "and"
                    val = self._eval_conditions(col.id, df, logic)
                    col_result[symbol] = val

                else:
                    col_result[symbol] = None

            result[col.id] = col_result

        return result

    # ------------------------------------------------------------------
    # Metadata refresh
    # ------------------------------------------------------------------

    async def _metadata_refresh_loop(self) -> None:
        """Periodically refresh symbol metadata and detect list membership changes."""
        try:
            while True:
                await asyncio.sleep(_METADATA_REFRESH_INTERVAL)
                try:
                    # Re-fetch metadata
                    new_metadata = await symbols_service.get_metadata_by_tickers(
                        self.realtime.manager.provider.fs, settings, self._symbols
                    )
                    self._metadata = new_metadata

                    # Re-evaluate filter in case list membership changed
                    if self.params.filter_active:
                        changed = await self._run_filter()
                        if changed:
                            await self._run_values()

                except Exception as e:
                    logger.warning(
                        "Metadata refresh failed for screener %s: %s",
                        self.session_id,
                        e,
                    )
        except asyncio.CancelledError:
            pass

    def __repr__(self) -> str:
        return f"ScreenerSession(id={self.session_id!r})"
