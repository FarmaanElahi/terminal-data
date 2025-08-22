"""
Core scanning engine that orchestrates the technical analysis process.

This is the main scanner component that coordinates between data providers,
expression evaluation, and result processing while remaining independent
of data sources.
"""

import logging
from typing import Dict, List, Any, Tuple
import pandas as pd

from modules.ezscan.interfaces.candle_provider import CandleProvider
from modules.ezscan.interfaces.stock_metadata_provider import StockMetadataProvider
from modules.ezscan.core.expression_evaluator import ExpressionEvaluator
from modules.ezscan.models.requests import Condition, ColumnDef, SortColumn

logger = logging.getLogger(__name__)


class ScannerEngine:
    """
    Main scanning engine that processes technical analysis requests.

    This class is independent of data sources and uses injected providers
    for both candle data and stock metadata.
    """

    def __init__(
            self,
            candle_provider: CandleProvider,
            metadata_provider: StockMetadataProvider,
            max_workers: int = 32,
            cache_enabled: bool = True
    ):
        """
        Initialize scanner engine with data providers.

        Args:
            candle_provider: Provider for OHLCV candle data
            metadata_provider: Provider for stock metadata
            max_workers: Maximum number of parallel workers
            cache_enabled: Whether to enable expression caching
        """
        self.candle_provider = candle_provider
        self.metadata_provider = metadata_provider
        self.expression_evaluator = ExpressionEvaluator(cache_enabled=cache_enabled)
        self.max_workers = max_workers

        # Load initial data
        self.symbol_data = self.candle_provider.load_data()
        logger.info(f"Scanner initialized with {len(self.symbol_data)} symbols, cache enabled: {cache_enabled}")

    def scan(
            self,
            conditions: List[Condition],
            columns: List[ColumnDef],
            logic: str = "and",
            sort_columns: List[SortColumn] = None
    ) -> Dict[str, Any]:
        """
        Execute technical scan with given conditions and columns.

        Args:
            conditions: List of technical conditions to evaluate
            columns: List of column definitions for output
            logic: Logic operator for combining conditions ('and' or 'or')
            sort_by: Single column name to sort by (legacy, deprecated)
            sort_columns: List of columns to sort by with direction

        Returns:
            Dict containing scan results with columns and data
        """
        if not self.symbol_data:
            return {"columns": ["symbol"] + [c.name for c in columns], "data": []}

        start_time = pd.Timestamp.now()

        # Step 1: Synchronous condition evaluation
        selected_symbols = self._evaluate_conditions_sync(conditions, logic)

        conditions_time = pd.Timestamp.now() - start_time

        if not selected_symbols:
            return {"columns": ["symbol"] + [c.name for c in columns], "data": []}

        # Step 2: Synchronous column evaluation
        columns_start = pd.Timestamp.now()
        rows = self._evaluate_columns_sync(selected_symbols, columns)
        columns_time = pd.Timestamp.now() - columns_start

        if not rows:
            return {"columns": ["symbol"] + [c.name for c in columns], "data": []}

        # Step 3: Process and sort results
        df_result = self._process_results(rows, columns, sort_columns)

        total_time = pd.Timestamp.now() - start_time

        logger.info(
            f"Synchronous scan completed: {len(selected_symbols)}/{len(self.symbol_data)} symbols, "
            f"conditions: {conditions_time.total_seconds():.3f}s, "
            f"columns: {columns_time.total_seconds():.3f}s, "
            f"total: {total_time.total_seconds():.3f}s"
        )

        return {
            "columns": df_result.columns.tolist(),
            "data": df_result.values.tolist()
        }

    def _evaluate_conditions_sync(self, conditions: List[Condition], logic: str) -> List[str]:
        """
        Evaluate conditions synchronously across all symbols.

        Args:
            conditions: List of conditions to evaluate
            logic: Logic operator ('and' or 'or')

        Returns:
            List[str]: Symbols that pass all conditions
        """
        selected_symbols = []

        for symbol in self.symbol_data.keys():
            args = (symbol, conditions, logic)
            symbol, passes = self._process_symbol_conditions(args)
            if passes:
                selected_symbols.append(symbol)

        return selected_symbols

    def _process_symbol_conditions(self, args: Tuple[str, List[Condition], str]) -> Tuple[str, bool]:
        """
        Process all conditions for a single symbol.

        Args:
            args: Tuple of (symbol, conditions, logic)

        Returns:
            Tuple[str, bool]: Symbol and whether it passes conditions
        """
        symbol, conditions, logic = args

        if symbol not in self.symbol_data:
            return symbol, False

        df = self.symbol_data[symbol]
        condition_results = []

        for condition in conditions:
            try:
                bool_series = self.expression_evaluator.evaluate_condition_expression(
                    symbol, df, condition.condition
                )
                result = self.expression_evaluator.reduce_condition_by_period(
                    bool_series, condition.evaluation_period, condition.value
                )
                condition_results.append(result)
            except Exception as e:
                logger.debug(f"Condition evaluation failed for {symbol}: {e}")
                condition_results.append(False)

        if not condition_results:
            return symbol, True

        # Apply logic operator
        if logic == "and":
            passes = all(condition_results)
        else:  # "or"
            passes = any(condition_results)

        return symbol, passes

    def _evaluate_columns_sync(self, symbols: List[str], columns: List[ColumnDef]) -> List[Dict[str, Any]]:
        """
        Evaluate columns synchronously for selected symbols.

        Args:
            symbols: List of symbols to process
            columns: List of column definitions

        Returns:
            List[Dict]: List of row dictionaries
        """
        rows = []

        for symbol in symbols:
            args = (symbol, columns)
            symbol, row = self._process_symbol_columns(args)
            if row is not None:
                rows.append(row)

        return rows

    def _process_symbol_columns(self, args: Tuple[str, List[ColumnDef]]) -> Tuple[str, Dict[str, Any]]:
        """
        Process all columns for a single symbol.

        Args:
            args: Tuple of (symbol, columns)

        Returns:
            Tuple[str, Dict]: Symbol and row data
        """
        symbol, columns = args

        if symbol not in self.symbol_data:
            return symbol, None

        df = self.symbol_data[symbol]
        row = {"symbol": symbol}

        for column in columns:
            if column.type == "evaluated":
                # Technical expression evaluation
                expr = (column.value or "").strip()
                if expr:
                    try:
                        value = self.expression_evaluator.evaluate_value_expression(
                            symbol, df, expr
                        )
                        row[column.name] = value
                    except Exception as e:
                        logger.debug(f"Column evaluation failed for {symbol}.{column.name}: {e}")
                        row[column.name] = None
                else:
                    row[column.name] = None

            elif column.type == "fixed":
                # Stock metadata
                try:
                    value = self.metadata_provider.get_metadata(symbol, column.prop)
                    row[column.name] = value
                except Exception as e:
                    logger.debug(f"Metadata retrieval failed for {symbol}.{column.prop}: {e}")
                    row[column.name] = None

        return symbol, row

    def _process_results(
            self,
            rows: List[Dict[str, Any]],
            columns: List[ColumnDef],
            sort_columns: List[SortColumn] = None
    ) -> pd.DataFrame:
        """
        Process and sort scan results with multi-column sorting support.

        Args:
            rows: List of row dictionaries
            columns: Column definitions
            sort_columns: List of columns to sort by with direction

        Returns:
            pd.DataFrame: Processed results
        """
        df_result = pd.DataFrame(rows)

        # Remove rows with all NaN evaluated columns
        evaluated_cols = [c.name for c in columns if c.type == "evaluated"]
        if evaluated_cols:
            df_result = df_result.dropna(subset=evaluated_cols, how='all')

        # Multi-column sorting
        if sort_columns:
            # Validate that all sort columns exist in the DataFrame
            available_columns = set(df_result.columns)
            valid_sort_columns = []

            for sort_col in sort_columns:
                if sort_col.column in available_columns:
                    valid_sort_columns.append(sort_col)
                else:
                    logger.warning(f"Sort column '{sort_col.column}' not found in results")

            if valid_sort_columns:
                # Prepare sorting parameters
                sort_column_names = [sc.column for sc in valid_sort_columns]
                sort_ascending = [sc.direction == "asc" for sc in valid_sort_columns]

                # Drop rows where any sort column has NaN values
                df_result = df_result.dropna(subset=sort_column_names)

                # Perform multi-column sort
                if not df_result.empty:
                    df_result = df_result.sort_values(
                        by=sort_column_names,
                        ascending=sort_ascending,
                        kind='mergesort',
                        na_position='last'
                    )

                    logger.info(f"Sorted by columns: {[(sc.column, sc.direction) for sc in valid_sort_columns]}")

        return df_result

    def get_available_symbols(self) -> List[str]:
        """Get list of available symbols."""
        return self.candle_provider.get_available_symbols()

    def get_symbol_info(self, symbol: str) -> Dict[str, Any]:
        """
        Get information about a specific symbol.

        Args:
            symbol: Symbol identifier

        Returns:
            Dict containing symbol information
        """
        df = self.candle_provider.get_symbol_data(symbol)
        if df is None:
            return {"error": "Symbol not found"}

        return {
            "symbol": symbol,
            "rows": len(df),
            "date_range": {
                "start": df.index[0].isoformat(),
                "end": df.index[-1].isoformat()
            },
            "latest": {
                "close": float(df["close"].iloc[-1]),
                "volume": int(df["volume"].iloc[-1]),
                "date": df.index[-1].isoformat()
            }
        }

    def refresh_data(self) -> None:
        """Refresh candle data from provider."""
        logger.info("Refreshing scanner data...")
        self.candle_provider.refresh_data()
        self.symbol_data = self.candle_provider.load_data()
        self.expression_evaluator.clear_cache()
        logger.info(f"Scanner refreshed with {len(self.symbol_data)} symbols")

    def enable_cache(self) -> None:
        """Enable expression caching."""
        self.expression_evaluator.enable_cache()

    def disable_cache(self) -> None:
        """Disable expression caching."""
        self.expression_evaluator.disable_cache()

    def is_cache_enabled(self) -> bool:
        """Check if caching is enabled."""
        return self.expression_evaluator.is_cache_enabled()

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache performance statistics."""
        stats = self.expression_evaluator.get_cache_stats()
        stats.update({
            "loaded_symbols": len(self.symbol_data),
            "max_workers": self.max_workers
        })
        return stats

    def clear_cache(self) -> None:
        """Clear expression cache."""
        self.expression_evaluator.clear_cache()
