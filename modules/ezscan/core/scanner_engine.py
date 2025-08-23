
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
from modules.ezscan.interfaces.metadata_provider import MetadataProvider
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
            metadata_provider: MetadataProvider,
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
        self.expression_evaluator = ExpressionEvaluator(cache_enabled=cache_enabled, metadata_provider=metadata_provider)
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
        Execute technical scan with 2-phase condition evaluation.

        Args:
            conditions: List of technical conditions to evaluate
            columns: List of column definitions for output
            logic: Logic operator for combining conditions ('and' or 'or')
            sort_columns: List of columns to sort by with direction

        Returns:
            Dict containing scan results with columns and data
        """
        if not self.symbol_data:
            return {"columns": ["symbol"] + [c.name for c in columns], "data": [], "count": 0, "success": False}

        start_time = pd.Timestamp.now()

        # Separate static and computed conditions
        static_conditions = [c for c in conditions if c.condition_type == "static"]
        computed_conditions = [c for c in conditions if c.condition_type == "computed"]

        # Phase 1: Static condition evaluation (metadata filtering)
        phase1_symbols = self._evaluate_static_conditions(static_conditions, logic)
        phase1_time = pd.Timestamp.now() - start_time

        logger.info(f"Phase 1 (static) completed: {len(phase1_symbols)}/{len(self.symbol_data)} symbols passed")

        if not phase1_symbols:
            return {"columns": ["symbol"] + [c.name for c in columns], "data": [], "count": 0, "success": False}

        # Phase 2: Computed condition evaluation (technical analysis)
        phase2_start = pd.Timestamp.now()
        if computed_conditions:
            selected_symbols = self._evaluate_computed_conditions(phase1_symbols, computed_conditions, logic)
        else:
            selected_symbols = phase1_symbols
        phase2_time = pd.Timestamp.now() - phase2_start

        logger.info(f"Phase 2 (computed) completed: {len(selected_symbols)}/{len(phase1_symbols)} symbols passed")

        if not selected_symbols:
            return {"columns": ["symbol"] + [c.name for c in columns], "data": [], "count": 0, "success": False}

        # Step 3: Column evaluation with vectorized static columns
        columns_start = pd.Timestamp.now()
        rows = self._evaluate_columns_vectorized(selected_symbols, columns)
        columns_time = pd.Timestamp.now() - columns_start

        if not rows:
            return {"columns": ["symbol"] + [c.name for c in columns], "data": [], "count": 0, "success": False}

        # Step 4: Process and sort results
        df_result = self._process_results(rows, columns, sort_columns)

        total_time = pd.Timestamp.now() - start_time

        logger.info(
            f"2-phase scan completed: {len(selected_symbols)}/{len(self.symbol_data)} symbols, "
            f"phase1 (static): {phase1_time.total_seconds():.3f}s, "
            f"phase2 (computed): {phase2_time.total_seconds():.3f}s, "
            f"columns: {columns_time.total_seconds():.3f}s, "
            f"total: {total_time.total_seconds():.3f}s"
        )

        return {
            "count": len(df_result),
            "columns": df_result.columns.tolist(),
            "data": df_result.values.tolist(),
            "success": True
        }

    def _evaluate_static_conditions(self, conditions: List[Condition], logic: str) -> List[str]:
        """
        Phase 1: Evaluate static conditions using vectorized metadata operations.

        Args:
            conditions: List of static conditions to evaluate
            logic: Logic operator ('and' or 'or')

        Returns:
            List[str]: Symbols that pass static conditions
        """
        if not conditions:
            # If no static conditions, return all symbols
            return list(self.symbol_data.keys())

        # Extract expressions from conditions
        expressions = [c.expression for c in conditions]
        symbols = list(self.symbol_data.keys())

        # Use vectorized evaluation
        return self.expression_evaluator.evaluate_static_conditions_vectorized(
            symbols, expressions, logic
        )

    def _evaluate_computed_conditions(self, symbols: List[str], conditions: List[Condition], logic: str) -> List[str]:
        """
        Phase 2: Evaluate computed conditions using OHLCV data.

        Args:
            symbols: List of symbols to evaluate (from phase 1)
            conditions: List of computed conditions to evaluate
            logic: Logic operator ('and' or 'or')

        Returns:
            List[str]: Symbols that pass computed conditions
        """
        if not conditions:
            return symbols

        selected_symbols = []

        for symbol in symbols:
            args = (symbol, conditions, logic)
            symbol, passes = self._process_symbol_computed_conditions(args)
            if passes:
                selected_symbols.append(symbol)

        return selected_symbols

    def _process_symbol_computed_conditions(self, args: Tuple[str, List[Condition], str]) -> Tuple[str, bool]:
        """
        Process computed conditions for a single symbol.

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
                    symbol, df, condition.expression
                )
                result = self.expression_evaluator.reduce_condition_by_period(
                    bool_series, condition.evaluation_period, condition.value
                )
                condition_results.append(result)
            except Exception as e:
                logger.debug(f"Computed condition evaluation failed for {symbol}: {e}")
                condition_results.append(False)

        if not condition_results:
            return symbol, True

        # Apply logic operator
        if logic == "and":
            passes = all(condition_results)
        else:  # "or"
            passes = any(condition_results)

        return symbol, passes

    def _evaluate_columns_vectorized(self, symbols: List[str], columns: List[ColumnDef]) -> List[Dict[str, Any]]:
        """
        Evaluate columns with vectorized approach for static columns and individual approach for computed/condition columns.

        Args:
            symbols: List of symbols to process
            columns: List of column definitions

        Returns:
            List[Dict]: List of row dictionaries
        """
        # Separate columns by type for optimization
        static_columns = [c for c in columns if c.type == "static"]
        computed_columns = [c for c in columns if c.type == "computed"]
        condition_columns = [c for c in columns if c.type == "condition"]

        # Initialize rows with symbols
        rows = [{"symbol": symbol} for symbol in symbols]

        # Step 1: Handle static columns in bulk (vectorized)
        if static_columns:
            static_start = pd.Timestamp.now()
            static_data = self._evaluate_static_columns_vectorized(symbols, static_columns)
            static_time = pd.Timestamp.now() - static_start
            logger.debug(f"Static columns evaluated in {static_time.total_seconds():.3f}s")
            
            # Merge static data into rows
            for i, symbol in enumerate(symbols):
                if symbol in static_data:
                    rows[i].update(static_data[symbol])

        # Step 2: Handle computed and condition columns individually
        non_static_columns = computed_columns + condition_columns
        if non_static_columns:
            computed_start = pd.Timestamp.now()
            for i, symbol in enumerate(symbols):
                symbol_data = self._evaluate_non_static_columns(symbol, non_static_columns)
                rows[i].update(symbol_data)
            computed_time = pd.Timestamp.now() - computed_start
            logger.debug(f"Non-static columns evaluated in {computed_time.total_seconds():.3f}s")

        return rows

    def _evaluate_static_columns_vectorized(self, symbols: List[str], static_columns: List[ColumnDef]) -> Dict[str, Dict[str, Any]]:
        """
        Evaluate static columns in bulk for maximum performance.

        Args:
            symbols: List of symbols to process
            static_columns: List of static column definitions

        Returns:
            Dict[str, Dict]: Nested dict with symbol -> {column_name: value}
        """
        try:
            # Get metadata DataFrame for all symbols at once
            metadata_df = self.metadata_provider.get_metadata_dataframe(symbols)
            
            result = {}
            
            # Process each symbol
            for symbol in symbols:
                symbol_data = {}
                
                if symbol in metadata_df.index:
                    # Symbol exists in metadata
                    symbol_row = metadata_df.loc[symbol]
                    
                    for column in static_columns:
                        try:
                            if column.property_name in metadata_df.columns:
                                value = symbol_row[column.property_name]
                                # Handle NaN values and convert to Python types
                                if pd.isna(value):
                                    symbol_data[column.name] = None
                                elif isinstance(value, (pd.Int64Dtype, pd.Float64Dtype)):
                                    symbol_data[column.name] = value.item()
                                else:
                                    symbol_data[column.name] = value
                            else:
                                logger.debug(f"Property '{column.property_name}' not found in metadata for column '{column.name}'")
                                symbol_data[column.name] = None
                        except Exception as e:
                            logger.debug(f"Error retrieving static column '{column.name}' for {symbol}: {e}")
                            symbol_data[column.name] = None
                else:
                    # Symbol not found in metadata, set all static columns to None
                    for column in static_columns:
                        symbol_data[column.name] = None
                
                result[symbol] = symbol_data
            
            return result
            
        except Exception as e:
            logger.warning(f"Vectorized static column evaluation failed, falling back to individual evaluation: {e}")
            return self._evaluate_static_columns_fallback(symbols, static_columns)

    def _evaluate_static_columns_fallback(self, symbols: List[str], static_columns: List[ColumnDef]) -> Dict[str, Dict[str, Any]]:
        """
        Fallback method for static column evaluation when vectorized approach fails.

        Args:
            symbols: List of symbols to process
            static_columns: List of static column definitions

        Returns:
            Dict[str, Dict]: Nested dict with symbol -> {column_name: value}
        """
        result = {}
        
        for symbol in symbols:
            symbol_data = {}
            for column in static_columns:
                try:
                    value = self.metadata_provider.get_metadata(symbol, column.property_name)
                    symbol_data[column.name] = value
                except Exception as e:
                    logger.debug(f"Static column '{column.name}' failed for {symbol}: {e}")
                    symbol_data[column.name] = None
            result[symbol] = symbol_data
        
        return result

    def _evaluate_non_static_columns(self, symbol: str, columns: List[ColumnDef]) -> Dict[str, Any]:
        """
        Evaluate computed and condition columns for a single symbol.

        Args:
            symbol: Symbol identifier
            columns: List of non-static column definitions

        Returns:
            Dict[str, Any]: Column name to value mapping
        """
        if symbol not in self.symbol_data:
            return {column.name: None for column in columns}

        df = self.symbol_data[symbol]
        result = {}

        for column in columns:
            try:
                if column.type == "computed":
                    # Computed expression column
                    expr = (column.expression or "").strip()
                    if expr:
                        value = self.expression_evaluator.evaluate_value_expression(
                            symbol, df, expr
                        )
                        result[column.name] = value
                    else:
                        result[column.name] = None

                elif column.type == "condition":
                    # Condition column using Condition objects
                    if column.conditions:
                        value = self.expression_evaluator.evaluate_condition_column(
                            symbol=symbol,
                            df=df,
                            conditions=column.conditions,
                            logic=column.logic or "and"
                        )
                        result[column.name] = value
                    else:
                        result[column.name] = False

                else:
                    logger.warning(f"Unknown column type '{column.type}' for column '{column.name}'")
                    result[column.name] = None

            except Exception as e:
                logger.debug(f"Column evaluation failed for {symbol}.{column.name}: {e}")
                result[column.name] = None

        return result

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
            sort_columns: List of columns to sort by with direction (references column IDs)

        Returns:
            pd.DataFrame: Processed results
        """
        df_result = pd.DataFrame(rows)

        # Remove rows with all NaN computed/condition columns
        non_static_cols = [c.name for c in columns if c.type in ["computed", "condition"]]
        if non_static_cols:
            # Only drop rows where ALL non-static columns are NaN
            df_result = df_result.dropna(subset=non_static_cols, how='all')

        # Multi-column sorting using column IDs
        if sort_columns:
            # Create mapping from column ID to column name
            id_to_name_map = {col.id: col.name for col in columns}
            # Add symbol column mapping
            id_to_name_map["symbol"] = "symbol"

            # Convert sort column IDs to actual column names
            available_columns = set(df_result.columns)
            valid_sort_columns = []
            sort_column_names = []

            for sort_col in sort_columns:
                # Check if sort_col.column is a column ID
                if sort_col.column in id_to_name_map:
                    actual_column_name = id_to_name_map[sort_col.column]
                    if actual_column_name in available_columns:
                        valid_sort_columns.append(sort_col)
                        sort_column_names.append(actual_column_name)
                    else:
                        logger.warning(f"Sort column with ID '{sort_col.column}' maps to '{actual_column_name}' but not found in results")
                else:
                    # Fallback: check if sort_col.column is directly a column name (for backward compatibility)
                    if sort_col.column in available_columns:
                        valid_sort_columns.append(sort_col)
                        sort_column_names.append(sort_col.column)
                        logger.info(f"Using column name directly for sorting: '{sort_col.column}'")
                    else:
                        logger.warning(f"Sort column ID/name '{sort_col.column}' not found in results")

            if valid_sort_columns:
                # Prepare sorting parameters
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

                    # Log with both IDs and names for clarity
                    sort_info = [(sc.column, id_to_name_map.get(sc.column, sc.column), sc.direction) for sc in valid_sort_columns]
                    logger.info(f"Sorted by columns: {sort_info}")

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