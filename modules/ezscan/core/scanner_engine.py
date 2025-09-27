import logging
from typing import Dict, List, Any, Tuple, Optional

import numpy as np
import pandas as pd

from modules.ezscan.core.expression_evaluator import ExpressionEvaluator
from modules.ezscan.models.requests import Condition, ColumnDef, SortColumn
from modules.ezscan.models.requests import ScanRequest
from modules.ezscan.providers.india_metadata_provider import IndiaMetadataProvider
from modules.ezscan.providers.us_metadata_provider import USMetadataProvider
from modules.ezscan.providers.tradingview_candle_provider import TradingViewCandleProvider

logger = logging.getLogger(__name__)


class ScannerEngine:
    """Orchestrates technical analysis with synchronous processing."""

    def __init__(self, cache_enabled: bool = True):
        self.candle_providers = {
            "india": TradingViewCandleProvider(market="india"),
            "us": TradingViewCandleProvider(market="us"),
        }
        self.metadata_providers = {
            "india": IndiaMetadataProvider(),
            "us": USMetadataProvider()
        }
        self.expression_evaluators = {
            market: ExpressionEvaluator(cache_enabled=cache_enabled, metadata_provider=provider)
            for market, provider in self.metadata_providers.items()
        }
        self.symbol_data = {}
        for market in self.candle_providers:
            self.symbol_data[market] = self.candle_providers[market].load_data()
        logger.info(f"Initialized with markets: {list(self.symbol_data.keys())}")

    def scan(self, request: ScanRequest) -> Dict[str, Any]:
        """Execute technical scan with 2-phase evaluation for specified market."""
        if request.market not in self.symbol_data:
            raise ValueError(f"Unsupported market: {request.market}")

        symbol_data = self.symbol_data[request.market]
        expression_evaluator = self.expression_evaluators[request.market]
        columns = request.columns

        # PreScan
        pre_scanned_symbols = self.perform_scan(request.pre_conditions, expression_evaluator, symbol_data, request.pre_condition_logic)
        if not pre_scanned_symbols:
            return {"columns": ["symbol"] + [c.name for c in columns], "data": [], "count": 0, "success": False}

        # Scan - Perform scan on prescanned result only
        symbol_data = {sym: symbol_data[sym] for sym in pre_scanned_symbols}
        scanned_symbols = self.perform_scan(request.conditions, expression_evaluator, symbol_data, request.logic)
        if not scanned_symbols:
            return {"columns": ["symbol"] + [c.name for c in columns], "data": [], "count": 0, "success": False}

        rows = self._evaluate_columns_vectorized(scanned_symbols, columns, expression_evaluator, request.market, symbol_data)

        if not rows:
            return {"columns": ["symbol"] + [c.name for c in columns], "data": [], "count": 0, "success": False}

        df_result = self._process_results(rows, columns, request.sort_columns)

        return {
            "count": len(df_result),
            "columns": df_result.columns.tolist(),
            "data": df_result.replace({np.nan: None}).values.tolist(),
            "success": True
        }

    def perform_scan(self, conditions: List[Condition], expression_evaluator: ExpressionEvaluator, symbol_data: dict[str, pd.DataFrame], logic: str = "and"):
        start_time = pd.Timestamp.now()
        static_conditions = [c for c in conditions if c.condition_type == "static"]
        computed_conditions = [c for c in conditions if c.condition_type == "computed"]

        phase1_symbols = self._evaluate_static_conditions(static_conditions, logic, expression_evaluator, symbol_data)
        phase1_time = pd.Timestamp.now() - start_time

        if not phase1_symbols:
            return None

        phase2_start = pd.Timestamp.now()
        selected_symbols = self._evaluate_computed_conditions(phase1_symbols, computed_conditions, logic, expression_evaluator, symbol_data)
        phase2_time = pd.Timestamp.now() - phase2_start

        return selected_symbols

    def _evaluate_static_conditions(self, conditions: List[Condition], logic: str, expression_evaluator: ExpressionEvaluator,
                                    symbol_data: Dict[str, pd.DataFrame]) -> List[str]:
        """Evaluate static conditions."""
        if not conditions:
            return list(symbol_data.keys())

        expressions = [c.expression for c in conditions]
        return expression_evaluator.evaluate_static_conditions_vectorized(
            list(symbol_data.keys()), expressions, logic
        )

    def _evaluate_computed_conditions(self, symbols: List[str], conditions: List[Condition], logic: str, expression_evaluator: ExpressionEvaluator,
                                      symbol_data: Dict[str, pd.DataFrame]) -> List[str]:
        """Evaluate computed conditions synchronously."""
        if not conditions:
            return symbols

        # Separate rank and boolean conditions
        rank_conditions = [c for c in conditions if c.evaluation_type == "rank"]
        boolean_conditions = [c for c in conditions if c.evaluation_type == "boolean"]

        filtered_symbols = symbols

        # Handle rank conditions vectorized
        if rank_conditions:
            rank_expressions = [c.expression for c in rank_conditions]
            rank_mins = [c.rank_min or 1 for c in rank_conditions]
            rank_maxes = [c.rank_max or 99 for c in rank_conditions]

            rank_selected = expression_evaluator.evaluate_rank_conditions_vectorized(
                filtered_symbols, rank_expressions, rank_mins, rank_maxes, symbol_data, logic
            )

            if logic == "and":
                filtered_symbols = [s for s in filtered_symbols if s in rank_selected]
            else:
                # For OR logic with mixed condition types, we need to handle it differently
                if not boolean_conditions:
                    filtered_symbols = rank_selected
                # If there are boolean conditions too, we'll handle the OR logic later

        # Handle boolean conditions
        if boolean_conditions:
            boolean_selected = []
            for symbol in filtered_symbols:
                if self._process_symbol_computed_conditions((symbol, boolean_conditions, logic, expression_evaluator, symbol_data))[1]:
                    boolean_selected.append(symbol)

            if logic == "and":
                filtered_symbols = boolean_selected
            elif rank_conditions:
                # OR logic: combine rank and boolean results
                rank_selected = expression_evaluator.evaluate_rank_conditions_vectorized(
                    symbols, [c.expression for c in rank_conditions],
                    [c.rank_min or 1 for c in rank_conditions],
                    [c.rank_max or 99 for c in rank_conditions], symbol_data, "or"
                ) if rank_conditions else []
                filtered_symbols = list(set(rank_selected + boolean_selected))
            else:
                filtered_symbols = boolean_selected

        return filtered_symbols

    def _process_symbol_computed_conditions(self, args: Tuple[str, List[Condition], str, ExpressionEvaluator, Dict[str, pd.DataFrame]]) -> Tuple[str, bool]:
        """Process computed conditions for a single symbol."""
        symbol, conditions, logic, expression_evaluator, symbol_data = args
        if symbol not in symbol_data:
            return symbol, False

        df = symbol_data[symbol]
        condition_results = []

        for condition in conditions:
            try:
                if condition.evaluation_type == "rank":
                    # Skip rank conditions here - they're handled vectorized in the parent method
                    continue
                else:
                    bool_series = expression_evaluator.evaluate_condition_expression(symbol, df, condition.expression)
                    result = expression_evaluator.reduce_condition_by_period(
                        bool_series, condition.evaluation_period, condition.value
                    )
                    condition_results.append(result)
            except Exception as e:
                logger.debug(f"Computed condition failed for {symbol}: {e}")
                condition_results.append(False)

        # If no boolean conditions, return True (rank conditions handled elsewhere)
        if not condition_results:
            return symbol, True

        return symbol, all(condition_results) if logic == "and" else any(condition_results)

    def _evaluate_columns_vectorized(self, symbols: List[str], columns: List[ColumnDef], expression_evaluator: ExpressionEvaluator, market: str,
                                     symbol_data: Dict[str, pd.DataFrame]) -> List[Dict[str, Any]]:
        """Evaluate columns with vectorized static columns."""
        static_columns = [c for c in columns if c.type == "static"]
        computed_columns = [c for c in columns if c.type == "computed"]
        condition_columns = [c for c in columns if c.type == "condition"]
        rows = [{"symbol": symbol} for symbol in symbols]

        if static_columns:
            static_start = pd.Timestamp.now()
            static_data = self._evaluate_static_columns_vectorized(symbols, static_columns, market)
            for i, symbol in enumerate(symbols):
                if symbol in static_data:
                    rows[i].update(static_data[symbol])
            logger.debug(f"Static columns evaluated in {(pd.Timestamp.now() - static_start).total_seconds():.3f}s")

        if computed_columns or condition_columns:
            computed_start = pd.Timestamp.now()
            for i, symbol in enumerate(symbols):
                rows[i].update(self._evaluate_non_static_columns((symbol, computed_columns + condition_columns, expression_evaluator, symbol_data)))
            logger.debug(f"Non-static columns evaluated in {(pd.Timestamp.now() - computed_start).total_seconds():.3f}s")

        return rows

    def _evaluate_static_columns_vectorized(self, symbols: List[str], static_columns: List[ColumnDef], market: str) -> Dict[str, Dict[str, Any]]:
        """Evaluate static columns vectorized."""
        try:
            metadata_df = self.metadata_providers[market].get_metadata_dataframe(symbols)
            result = {}
            for symbol in symbols:
                symbol_data = {}
                if symbol in metadata_df.index:
                    symbol_row = metadata_df.loc[symbol]
                    for column in static_columns:
                        value = symbol_row.get(column.property_name, None)
                        symbol_data[column.name] = None if pd.isna(value) else value
                else:
                    symbol_data = {column.name: None for column in static_columns}
                result[symbol] = symbol_data
            return result
        except Exception as e:
            logger.warning(f"Vectorized static column evaluation failed for {market}: {e}", exc_info=True)
            return self._evaluate_static_columns_fallback(symbols, static_columns, market)

    def _evaluate_static_columns_fallback(self, symbols: List[str], static_columns: List[ColumnDef], market: str) -> Dict[str, Dict[str, Any]]:
        """Fallback for static column evaluation."""
        result = {}
        for symbol in symbols:
            symbol_data = {}
            for column in static_columns:
                try:
                    value = self.metadata_providers[market].get_metadata(symbol, column.property_name)
                    symbol_data[column.name] = value
                except Exception:
                    symbol_data[column.name] = None
            result[symbol] = symbol_data
        return result

    def _evaluate_non_static_columns(self, args: Tuple[str, List[ColumnDef], ExpressionEvaluator, Dict[str, pd.DataFrame]]) -> Dict[str, Any]:
        """Evaluate non-static columns."""
        symbol, columns, expression_evaluator, symbol_data = args
        if symbol not in symbol_data:
            return {column.name: None for column in columns}

        df = symbol_data[symbol]
        result = {}
        for column in columns:
            try:
                if column.type == "computed" and column.expression:
                    result[column.name] = expression_evaluator.evaluate_value_expression(symbol, df, column.expression)
                elif column.type == "condition" and column.conditions:
                    result[column.name] = expression_evaluator.evaluate_condition_column(
                        symbol, df, column.conditions, column.logic or "and", symbol_data
                    )
                else:
                    result[column.name] = None
            except Exception as e:
                logger.debug(f"Column {column.name} failed for {symbol}: {e}")
                result[column.name] = None
        return result

    def _process_results(self, rows: List[Dict[str, Any]], columns: List[ColumnDef],
                         sort_columns: List[SortColumn] | None = None) -> pd.DataFrame:
        """Process and sort results."""
        df_result = pd.DataFrame(rows)
        non_static_cols = [c.name for c in columns if c.type in ["computed", "condition"]]
        if non_static_cols:
            df_result = df_result.dropna(subset=non_static_cols, how='all')

        if sort_columns:
            id_to_name_map = {col.id: col.name for col in columns}
            id_to_name_map["symbol"] = "symbol"
            sort_column_names = []
            sort_ascending = []

            for sort_col in sort_columns:
                col_name = id_to_name_map.get(sort_col.column, sort_col.column)
                if col_name in df_result.columns:
                    sort_column_names.append(col_name)
                    sort_ascending.append(sort_col.direction == "asc")

            if sort_column_names:
                df_result = df_result.dropna(subset=sort_column_names)
                if not df_result.empty:
                    df_result = df_result.sort_values(
                        by=sort_column_names, ascending=sort_ascending, kind='mergesort', na_position='last'
                    )

        final_column_order = ["symbol"] + [c.name for c in columns]
        final_column_order = [col for col in final_column_order if col in df_result.columns]
        remaining_columns = [col for col in df_result.columns if col not in final_column_order]
        return df_result[final_column_order + remaining_columns]

    def get_available_symbols(self, market: str = "india") -> List[str]:
        """Get available symbols for a market."""
        if market not in self.candle_providers:
            raise ValueError(f"Unsupported market: {market}")
        return self.candle_providers[market].get_available_symbols()

    def get_symbol_info(self, symbol: str, market: str = "india") -> Dict[str, Any]:
        """Get symbol information for a market."""
        if market not in self.candle_providers:
            raise ValueError(f"Unsupported market: {market}")
        df = self.candle_providers[market].get_symbol_data(symbol)
        if df is None or df.empty:
            return {"error": "Symbol not found"}

        return {
            "symbol": symbol,
            "rows": len(df),
            "date_range": {"start": df.index[0].isoformat(), "end": df.index[-1].isoformat()},
            "latest": {"close": float(df["close"].iloc[-1]), "volume": int(df["volume"].iloc[-1]),
                       "date": df.index[-1].isoformat()}
        }

    def refresh_data(self, market: Optional[str] = None) -> None:
        """Refresh data for a specific market or all markets."""
        logger.info(f"Refreshing scanner data for {'all markets' if market is None else market}...")
        markets = [market] if market else list(self.candle_providers.keys())
        for m in markets:
            if m in self.candle_providers:
                self.symbol_data[m] = self.candle_providers[m].refresh_data()
                self.metadata_providers[m].refresh_metadata()
                self.expression_evaluators[m].clear_cache()
                logger.info(f"Refreshed {m} with {len(self.symbol_data[m])} symbols")
            else:
                logger.warning(f"Skipping unsupported market: {m}")

    def enable_cache(self) -> None:
        """Enable caching for all evaluators."""
        for evaluator in self.expression_evaluators.values():
            evaluator.enable_cache()

    def disable_cache(self) -> None:
        """Disable caching for all evaluators."""
        for evaluator in self.expression_evaluators.values():
            evaluator.disable_cache()

    def is_cache_enabled(self) -> bool:
        """Check if caching is enabled (checks first evaluator)."""
        return next(iter(self.expression_evaluators.values())).is_cache_enabled()

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics aggregated across markets."""
        stats = {}
        for market, evaluator in self.expression_evaluators.items():
            market_stats = evaluator.get_cache_stats()
            market_stats["loaded_symbols"] = len(self.symbol_data.get(market, {}))
            stats[market] = market_stats
        return stats

    def clear_cache(self) -> None:
        """Clear cache for all evaluators."""
        for evaluator in self.expression_evaluators.values():
            evaluator.clear_cache()
