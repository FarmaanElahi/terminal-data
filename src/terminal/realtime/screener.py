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
from terminal.formula import FormulaError, can_scalar_eval, compute_lookback, evaluate, parse, scalar_last
from terminal.formula.ast_nodes import FieldRef
from terminal.formula.scalar import _Unsupported
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
        self._start_task: asyncio.Task | None = None
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
        # Fire _start() as a background task so the WebSocket message loop
        # can immediately read and process the next message (e.g. chart setup)
        # without waiting 3–5s for the screener to fully initialise.
        self._start_task = asyncio.create_task(self._start_safe())

    async def _handle_modify_screener(self, msg: ModifyScreenerRequest) -> None:
        """Handle a modify_screener request."""
        _, params = msg.p
        self.stop()
        self.params = params
        self._start_task = asyncio.create_task(self._start_safe())

    async def _start_safe(self) -> None:
        """Wrapper around _start() that logs unhandled exceptions from the task."""
        try:
            await self._start()
        except Exception:
            logger.exception("Screener %s startup failed", self.session_id)

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

        # _run_filter(force=True) evaluates all columns and seeds _last_values.
        # Calling _run_values right after would re-evaluate everything and diff
        # to zero changes — pure wasted work. Skip it.
        try:
            t0 = time.perf_counter()
            await self._run_filter(force=True)
            logger.info(
                "Screener %s [initial_eval/run_filter] %.0fms",
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
        if self._start_task and not self._start_task.done():
            self._start_task.cancel()
            self._start_task = None
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
        """Pre-parse all formula ASTs and inline condition formulas at start time.

        Each parsed entry is a 3-tuple ``(col_or_cond, ast, lookback)`` where
        ``lookback`` is the minimum number of DataFrame rows needed for the last
        element of ``evaluate(ast, df)`` to be valid.  This is used to slice the
        DataFrame before evaluation, avoiding CPU work on irrelevant history.

        Also computes ``_max_lb_per_tf`` — the maximum lookback across all
        non-FieldRef columns for each timeframe.  Used to build the smallest
        possible DataFrame when populating the per-symbol df_cache.
        """
        self._formula_errors = []

        # Parse value column formulas — tuple: (col, ast, lookback, can_scalar)
        # can_scalar=True means the formula can be evaluated by scalar_last()
        # without allocating a DataFrame at all.
        self._parsed_columns = []
        for col in self._columns:
            if col.type == "value" and col.value_formula:
                try:
                    ast = parse(col.value_formula)
                    # bar_ago shifts the read index back, so add it to the lookback
                    lb = compute_lookback(ast) + (col.value_formula_x_bar_ago or 0)
                    # Scalar fast path: no bar_ago needed because scalar_last
                    # handles offsets from the last element natively; bar_ago
                    # would need a different index, so disable scalar for those.
                    sc = can_scalar_eval(ast) and not (col.value_formula_x_bar_ago or 0)
                    self._parsed_columns.append((col, ast, lb, sc))
                except FormulaError as e:
                    logger.warning("Column formula parse error: %s", e.message)
                    self._parsed_columns.append((col, None, 500, False))
                    self._formula_errors.append(
                        ScreenerErrorInfo(column_id=col.id, message=e.message)
                    )
            else:
                self._parsed_columns.append((col, None, 1, False))

        # Parse inline condition formulas — tuple: (cond, ast, lookback)
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
                    lb = compute_lookback(ast)
                    parsed.append((cond, ast, lb))
                except (FormulaError, Exception):
                    parsed.append((cond, None, 500))
            self._parsed_conditions[col.id] = parsed

        # Pre-compute the maximum lookback per timeframe across all columns that
        # actually need a DataFrame (i.e. not handled by the scalar / FieldRef
        # fast paths).  This lets us build the smallest possible DataFrame in
        # the df_cache rather than the full 1825-row history.
        self._max_lb_per_tf: dict[str, int] = {}
        for col, col_ast, col_lb, col_sc in self._parsed_columns:
            if col.type == "value":
                tf = col.value_formula_tf or "D"
                bar_ago = col.value_formula_x_bar_ago or 0
                # Both the FieldRef fast path and the scalar fast path skip
                # DataFrame construction — only count columns that need one.
                if col_ast is None or col_sc or (not bar_ago and isinstance(col_ast, FieldRef)):
                    continue
                self._max_lb_per_tf[tf] = max(self._max_lb_per_tf.get(tf, 0), col_lb)
            elif col.type == "condition":
                tf = col.conditions_tf or "D"
                max_cond_lb = max(
                    (lb for _, _, lb in self._parsed_conditions.get(col.id, [])),
                    default=1,
                )
                self._max_lb_per_tf[tf] = max(
                    self._max_lb_per_tf.get(tf, 0), max_cond_lb
                )

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

            # Get initial values for the "full dataframe" response.
            # CPU-bound — run in thread pool so the event loop stays responsive.
            t0 = time.perf_counter()
            loop = asyncio.get_running_loop()
            initial_values = await loop.run_in_executor(None, self._evaluate_columns)
            logger.info(
                "Screener %s [run_filter/evaluate_columns] %.0fms — %d cols × %d rows",
                self.session_id,
                (time.perf_counter() - t0) * 1000,
                len(initial_values),
                len(self._visible_tickers),
            )
            self._last_values.update(initial_values)

            ticker_index = {t: i for i, t in enumerate(self._visible_tickers)}
            rows: list[ScreenerFilterRow] = []
            for t in self._visible_tickers:
                meta = self._metadata.get(t, {})
                i = ticker_index[t]
                row_values = {cid: vals[i] for cid, vals in initial_values.items()}
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
        for cond, ast, lb in parsed:
            if ast is None:
                results.append(False)
                continue
            try:
                df_slice = df.iloc[-lb:] if lb < len(df) else df
                result = evaluate(ast, df_slice)
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

    def _get_df_for_eval(
        self, manager: Any, symbol: str, tf: str
    ) -> "pd.DataFrame | None":
        """Return the smallest DataFrame needed to evaluate all columns for *tf*.

        For the daily timeframe, reads exactly ``_max_lb_per_tf[tf]`` rows from
        the numpy buffer — no unnecessary history is allocated.  Falls back to
        the full ``get_ohlcv()`` path for weekly/monthly (which requires pandas
        resampling from full daily data) and when the symbol is not yet in the
        store.
        """
        max_lb = self._max_lb_per_tf.get(tf, 0)
        if tf == "D" and max_lb > 0:
            df = manager.store.get_last_n_data(symbol, max_lb)
            if df is not None:
                return df
        # Fallback: weekly/monthly resampling or symbol not pre-loaded
        return manager.get_ohlcv(symbol, timeframe=tf)

    async def _run_values(self) -> None:
        """Evaluate all column formulas for visible tickers and emit only changed columns."""
        if not self._visible_tickers or not self._columns:
            return

        loop = asyncio.get_running_loop()
        values_map = await loop.run_in_executor(None, self._evaluate_columns)
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
        """Compute column values for all visible tickers using cached ASTs.

        Iterates symbols in the outer loop so that a single ``get_ohlcv()``
        call (and its ``pd.DataFrame`` construction) is shared across all
        columns that use the same timeframe for a given symbol.

        For simple ``FieldRef`` columns on the daily timeframe (e.g. ``C``,
        ``V``) the fast path reads directly from the numpy buffer — no
        DataFrame is allocated at all.
        """
        manager = self.realtime.manager
        n = len(self._visible_tickers)

        # Pre-allocate result lists — avoids repeated .append() calls
        values_map: dict[str, list[Any]] = {
            col.id: [None] * n for col, _, _, _ in self._parsed_columns
        }

        for i, symbol in enumerate(self._visible_tickers):
            # One DataFrame per (symbol, timeframe) — shared across all columns
            df_cache: dict[str, pd.DataFrame | None] = {}
            # Raw numpy buffer for the scalar fast path (populated on first access)
            _scalar_buf: tuple[np.ndarray, int] | None | bool = False  # False = not yet loaded

            for col, col_ast, col_lb, col_sc in self._parsed_columns:
                if col.type == "value":
                    if col.value_type == "field":
                        meta = self._metadata.get(symbol, {})
                        values_map[col.id][i] = meta.get(col.id)
                        continue

                    if col_ast is None:
                        continue  # already None in pre-allocated list

                    tf = col.value_formula_tf or "D"
                    bar_ago = col.value_formula_x_bar_ago or 0

                    # ── Scalar fast path: zero DataFrame allocation ──────────
                    # Works for any pure-arithmetic formula on daily TF fields.
                    if col_sc and tf == "D":
                        if _scalar_buf is False:
                            key = (symbol, "1D")
                            s = manager.store._sizes.get(key, 0)
                            _scalar_buf = (manager.store._ohlcv[key], s) if s > 0 else None
                        if _scalar_buf is not None:
                            ohlcv_arr, sz = _scalar_buf
                            try:
                                val = scalar_last(col_ast, ohlcv_arr, sz)
                                values_map[col.id][i] = val
                                continue
                            except _Unsupported:
                                pass  # fall through to DataFrame path

                    # ── FieldRef fast path: single O(1) numpy element read ───
                    if not bar_ago and tf == "D" and isinstance(col_ast, FieldRef):
                        val = manager.store.get_last_field(symbol, col_ast.name)
                        if val is not None:
                            values_map[col.id][i] = val
                        continue

                    # ── General path: build (minimal) DataFrame ──────────────
                    if tf not in df_cache:
                        df_cache[tf] = self._get_df_for_eval(manager, symbol, tf)
                    df = df_cache[tf]

                    if df is None or len(df) == 0:
                        continue

                    try:
                        df_slice = df.iloc[-col_lb:] if col_lb < len(df) else df
                        res = evaluate(col_ast, df_slice)
                        res = np.asarray(res)

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

                        values_map[col.id][i] = val
                    except (FormulaError, Exception) as e:
                        logger.warning(
                            "Column %s eval failed for %s: %s", col.id, symbol, e
                        )
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
                    if tf not in df_cache:
                        df_cache[tf] = self._get_df_for_eval(manager, symbol, tf)
                    df = df_cache[tf]

                    if df is None or len(df) == 0:
                        values_map[col.id][i] = False
                        continue

                    logic = col.conditions_logic or "and"
                    values_map[col.id][i] = self._eval_conditions(col.id, df, logic)

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

        Uses the same symbol-outer / df_cache / FieldRef fast-path optimisations
        as ``_evaluate_columns()``.
        """
        manager = self.realtime.manager
        result: dict[str, dict[str, Any]] = {
            col.id: {} for col, _, _, _ in self._parsed_columns
        }

        for symbol in symbols:
            df_cache: dict[str, pd.DataFrame | None] = {}
            _scalar_buf: tuple[np.ndarray, int] | None | bool = False

            for col, col_ast, col_lb, col_sc in self._parsed_columns:
                if col.type == "value":
                    if col.value_type == "field":
                        meta = self._metadata.get(symbol, {})
                        result[col.id][symbol] = meta.get(col.id)
                        continue

                    if col_ast is None:
                        result[col.id][symbol] = None
                        continue

                    tf = col.value_formula_tf or "D"
                    bar_ago = col.value_formula_x_bar_ago or 0

                    # Scalar fast path
                    if col_sc and tf == "D":
                        if _scalar_buf is False:
                            key = (symbol, "1D")
                            s = manager.store._sizes.get(key, 0)
                            _scalar_buf = (manager.store._ohlcv[key], s) if s > 0 else None
                        if _scalar_buf is not None:
                            ohlcv_arr, sz = _scalar_buf
                            try:
                                result[col.id][symbol] = scalar_last(col_ast, ohlcv_arr, sz)
                                continue
                            except _Unsupported:
                                pass

                    # FieldRef fast path
                    if not bar_ago and tf == "D" and isinstance(col_ast, FieldRef):
                        result[col.id][symbol] = manager.store.get_last_field(symbol, col_ast.name)
                        continue

                    if tf not in df_cache:
                        df_cache[tf] = self._get_df_for_eval(manager, symbol, tf)
                    df = df_cache[tf]

                    if df is None or len(df) == 0:
                        result[col.id][symbol] = None
                        continue

                    try:
                        df_slice = df.iloc[-col_lb:] if col_lb < len(df) else df
                        res = evaluate(col_ast, df_slice)
                        res = np.asarray(res)

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

                        result[col.id][symbol] = val
                    except (FormulaError, Exception) as e:
                        logger.warning(
                            "Column %s eval failed for %s: %s", col.id, symbol, e
                        )
                        result[col.id][symbol] = None

                elif col.type == "condition":
                    tf = col.conditions_tf or "D"
                    if tf not in df_cache:
                        df_cache[tf] = self._get_df_for_eval(manager, symbol, tf)
                    df = df_cache[tf]

                    if df is None or len(df) == 0:
                        result[col.id][symbol] = False
                        continue

                    logic = col.conditions_logic or "and"
                    result[col.id][symbol] = self._eval_conditions(col.id, df, logic)

                else:
                    result[col.id][symbol] = None

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
