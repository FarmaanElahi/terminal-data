import logging
from typing import Dict, List, Any, Tuple, Optional
import pandas as pd
import numpy as np
from modules.ezscan.interfaces.candle_provider import CandleProvider
from modules.ezscan.interfaces.metadata_provider import MetadataProvider
from modules.ezscan.core.expression_evaluator import ExpressionEvaluator
from modules.ezscan.models.requests import Condition, ColumnDef, SortColumn

logger = logging.getLogger(__name__)


class ScannerEngine:
    """Orchestrates technical analysis with synchronous processing."""

    def __init__(self, candle_provider: CandleProvider, metadata_provider: MetadataProvider,
                 cache_enabled: bool = True):
        self.candle_provider = candle_provider
        self.metadata_provider = metadata_provider
        self.expression_evaluator = ExpressionEvaluator(cache_enabled=cache_enabled, metadata_provider=metadata_provider)
        self.symbol_data = self.candle_provider.load_data()
        logger.info(f"Initialized with {len(self.symbol_data)} symbols")

    def scan(self, conditions: List[Condition], columns: List[ColumnDef],
             logic: str = "and", sort_columns: Optional[List[SortColumn]] = None) -> Dict[str, Any]:
        """Execute technical scan with 2-phase evaluation."""
        if not self.symbol_data:
            return {"columns": ["symbol"] + [c.name for c in columns], "data": [], "count": 0, "success": False}

        start_time = pd.Timestamp.now()
        static_conditions = [c for c in conditions if c.condition_type == "static"]
        computed_conditions = [c for c in conditions if c.condition_type == "computed"]

        phase1_symbols = self._evaluate_static_conditions(static_conditions, logic)
        phase1_time = pd.Timestamp.now() - start_time

        if not phase1_symbols:
            return {"columns": ["symbol"] + [c.name for c in columns], "data": [], "count": 0, "success": False}

        phase2_start = pd.Timestamp.now()
        selected_symbols = self._evaluate_computed_conditions(phase1_symbols, computed_conditions, logic)
        phase2_time = pd.Timestamp.now() - phase2_start

        if not selected_symbols:
            return {"columns": ["symbol"] + [c.name for c in columns], "data": [], "count": 0, "success": False}

        columns_start = pd.Timestamp.now()
        rows = self._evaluate_columns_vectorized(selected_symbols, columns)
        columns_time = pd.Timestamp.now() - columns_start

        if not rows:
            return {"columns": ["symbol"] + [c.name for c in columns], "data": [], "count": 0, "success": False}

        df_result = self._process_results(rows, columns, sort_columns)

        total_time = pd.Timestamp.now() - start_time
        logger.info(
            f"Scan completed: {len(selected_symbols)}/{len(self.symbol_data)} symbols, "
            f"phase1: {phase1_time.total_seconds():.3f}s, phase2: {phase2_time.total_seconds():.3f}s, "
            f"columns: {columns_time.total_seconds():.3f}s, total: {total_time.total_seconds():.3f}s"
        )

        return {
            "count": len(df_result),
            "columns": df_result.columns.tolist(),
            "data": df_result.replace({np.nan: None}).values.tolist(),
            "success": True
        }

    def _evaluate_static_conditions(self, conditions: List[Condition], logic: str) -> List[str]:
        """Evaluate static conditions."""
        if not conditions:
            return list(self.symbol_data.keys())

        expressions = [c.expression for c in conditions]
        return self.expression_evaluator.evaluate_static_conditions_vectorized(
            list(self.symbol_data.keys()), expressions, logic
        )

    def _evaluate_computed_conditions(self, symbols: List[str], conditions: List[Condition], logic: str) -> List[str]:
        """Evaluate computed conditions synchronously."""
        if not conditions:
            return symbols

        selected_symbols = []
        for symbol in symbols:
            if self._process_symbol_computed_conditions((symbol, conditions, logic))[1]:
                selected_symbols.append(symbol)
        return selected_symbols

    def _process_symbol_computed_conditions(self, args: Tuple[str, List[Condition], str]) -> Tuple[str, bool]:
        """Process computed conditions for a single symbol."""
        symbol, conditions, logic = args
        if symbol not in self.symbol_data:
            return symbol, False

        df = self.symbol_data[symbol]
        condition_results = []

        for condition in conditions:
            try:
                bool_series = self.expression_evaluator.evaluate_condition_expression(symbol, df, condition.expression)
                result = self.expression_evaluator.reduce_condition_by_period(
                    bool_series, condition.evaluation_period, condition.value
                )
                condition_results.append(result)
            except Exception as e:
                logger.debug(f"Computed condition failed for {symbol}: {e}")
                condition_results.append(False)

        return symbol, all(condition_results) if logic == "and" else any(condition_results)

    def _evaluate_columns_vectorized(self, symbols: List[str], columns: List[ColumnDef]) -> List[Dict[str, Any]]:
        """Evaluate columns with vectorized static columns."""
        static_columns = [c for c in columns if c.type == "static"]
        computed_columns = [c for c in columns if c.type == "computed"]
        condition_columns = [c for c in columns if c.type == "condition"]
        rows = [{"symbol": symbol} for symbol in symbols]

        if static_columns:
            static_start = pd.Timestamp.now()
            static_data = self._evaluate_static_columns_vectorized(symbols, static_columns)
            for i, symbol in enumerate(symbols):
                if symbol in static_data:
                    rows[i].update(static_data[symbol])
            logger.debug(f"Static columns evaluated in {(pd.Timestamp.now() - static_start).total_seconds():.3f}s")

        if computed_columns or condition_columns:
            computed_start = pd.Timestamp.now()
            for i, symbol in enumerate(symbols):
                rows[i].update(self._evaluate_non_static_columns((symbol, computed_columns + condition_columns)))
            logger.debug(f"Non-static columns evaluated in {(pd.Timestamp.now() - computed_start).total_seconds():.3f}s")

        return rows

    def _evaluate_static_columns_vectorized(self, symbols: List[str], static_columns: List[ColumnDef]) -> Dict[str, Dict[str, Any]]:
        """Evaluate static columns vectorized."""
        try:
            metadata_df = self.metadata_provider.get_metadata_dataframe(symbols)
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
            logger.warning(f"Vectorized static column evaluation failed: {e}", exc_info=True)
            return self._evaluate_static_columns_fallback(symbols, static_columns)

    def _evaluate_static_columns_fallback(self, symbols: List[str], static_columns: List[ColumnDef]) -> Dict[str, Dict[str, Any]]:
        """Fallback for static column evaluation."""
        result = {}
        for symbol in symbols:
            symbol_data = {}
            for column in static_columns:
                try:
                    value = self.metadata_provider.get_metadata(symbol, column.property_name)
                    symbol_data[column.name] = value
                except Exception:
                    symbol_data[column.name] = None
            result[symbol] = symbol_data
        return result

    def _evaluate_non_static_columns(self, args: Tuple[str, List[ColumnDef]]) -> Dict[str, Any]:
        """Evaluate non-static columns."""
        symbol, columns = args
        if symbol not in self.symbol_data:
            return {column.name: None for column in columns}

        df = self.symbol_data[symbol]
        result = {}
        for column in columns:
            try:
                if column.type == "computed" and column.expression:
                    result[column.name] = self.expression_evaluator.evaluate_value_expression(symbol, df, column.expression)
                elif column.type == "condition" and column.conditions:
                    result[column.name] = self.expression_evaluator.evaluate_condition_column(
                        symbol, df, column.conditions, column.logic or "and"
                    )
                else:
                    result[column.name] = None
            except Exception as e:
                logger.debug(f"Column {column.name} failed for {symbol}: {e}")
                result[column.name] = None
        return result

    def _process_results(self, rows: List[Dict[str, Any]], columns: List[ColumnDef],
                         sort_columns: Optional[List[SortColumn]] = None) -> pd.DataFrame:
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

    def get_available_symbols(self) -> List[str]:
        """Get available symbols."""
        return list(self.symbol_data.keys())

    def get_symbol_info(self, symbol: str) -> Dict[str, Any]:
        """Get symbol information."""
        df = self.candle_provider.get_symbol_data(symbol)
        if df is None or df.empty:
            return {"error": "Symbol not found"}

        return {
            "symbol": symbol,
            "rows": len(df),
            "date_range": {"start": df.index[0].isoformat(), "end": df.index[-1].isoformat()},
            "latest": {"close": float(df["close"].iloc[-1]), "volume": int(df["volume"].iloc[-1]),
                       "date": df.index[-1].isoformat()}
        }

    def refresh_data(self) -> None:
        """Refresh data."""
        logger.info("Refreshing scanner data...")
        self.symbol_data = self.candle_provider.refresh_data()
        self.metadata_provider.refresh_metadata()
        self.expression_evaluator.clear_cache()
        logger.info(f"Refreshed with {len(self.symbol_data)} symbols")

    def enable_cache(self) -> None:
        """Enable caching."""
        self.expression_evaluator.enable_cache()

    def disable_cache(self) -> None:
        """Disable caching."""
        self.expression_evaluator.disable_cache()

    def is_cache_enabled(self) -> bool:
        """Check if caching is enabled."""
        return self.expression_evaluator.is_cache_enabled()

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        stats = self.expression_evaluator.get_cache_stats()
        stats.update({"loaded_symbols": len(self.symbol_data)})
        return stats

    def clear_cache(self) -> None:
        """Clear cache."""
        self.expression_evaluator.clear_cache()
