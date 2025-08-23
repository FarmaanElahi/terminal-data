"""
Expression evaluation engine for technical analysis.

Handles the evaluation of technical expressions against symbol data
with caching for performance optimization.
"""

import logging
from typing import Dict, Any, Optional, List, Literal
import pandas as pd

from modules.ezscan.core.technical_indicators import (
    sma_single, ema_single, prv_single, min_single, max_single,
    count_single, count_true_single
)
from modules.ezscan.interfaces.stock_metadata_provider import StockMetadataProvider
from modules.ezscan.utils.cache import ExpressionCache

logger = logging.getLogger(__name__)


class ExpressionEvaluator:
    """
    Evaluates technical expressions against symbol OHLCV data.

    This class handles both value expressions (returning a single value)
    and condition expressions (returning boolean series for period evaluation).
    """

    def __init__(self, cache_enabled: bool = True, metadata_provider: Optional[StockMetadataProvider] = None):
        """Initialize the expression evaluator with cache."""
        self.cache = ExpressionCache(enabled=cache_enabled)
        self.metadata_provider = metadata_provider

    def evaluate_value_expression(self, symbol: str, df: pd.DataFrame, expression: str) -> float:
        """
        Evaluate expression and return the last value.

        Args:
            symbol: Symbol identifier for caching
            df: OHLCV DataFrame for the symbol
            expression: Technical expression to evaluate

        Returns:
            float: Last value of the evaluated expression
        """
        cache_key = f"{symbol}_val_{hash(expression)}"

        if cached_result := self.cache.get(cache_key):
            return cached_result

        try:
            result = self._evaluate_expression(symbol, df, expression)

            # Get last value
            if isinstance(result, pd.Series):
                last_val = result.iloc[-1] if len(result) > 0 else pd.NA
            else:
                last_val = result

            # Convert pandas NA to Python None for JSON serialization
            if pd.isna(last_val):
                last_val = None

            self.cache.set(cache_key, last_val)
            return last_val

        except Exception as e:
            logger.debug(f"Expression '{expression}' failed for {symbol}: {e}")
            self.cache.set(cache_key, None)
            return None

    def evaluate_condition_expression(self, symbol: str, df: pd.DataFrame, expression: str) -> pd.Series:
        """
        Evaluate condition expression and return boolean series.

        Args:
            symbol: Symbol identifier for caching
            df: OHLCV DataFrame for the symbol
            expression: Condition expression to evaluate

        Returns:
            pd.Series: Boolean series for period evaluation
        """
        cache_key = f"{symbol}_cond_{hash(expression)}"

        cached_result = self.cache.get(cache_key)

        if cached_result is not None:
            return cached_result

        try:
            result = self._evaluate_expression(symbol, df, expression)

            if isinstance(result, pd.Series):
                bool_series = result.astype(bool)
            else:
                # Scalar result - broadcast to series
                bool_series = pd.Series([bool(result)] * len(df), index=df.index, dtype=bool)

            self.cache.set(cache_key, bool_series)
            return bool_series

        except Exception as e:
            logger.debug(f"Condition '{expression}' failed for {symbol}: {e}")
            # Return False series
            false_series = pd.Series(False, index=df.index, dtype=bool)
            self.cache.set(cache_key, false_series)
            return false_series

    def evaluate_static_conditions_vectorized(self, symbols: List[str], expressions: List[str], logic: str = "and") -> List[str]:
        """
        Evaluate static conditions in a vectorized manner using DataFrame operations.

        Args:
            symbols: List of symbols to evaluate
            expressions: List of static expressions to evaluate
            logic: Logic operator ('and' or 'or')

        Returns:
            List[str]: Symbols that pass static conditions
        """
        if not expressions or not self.metadata_provider:
            return symbols

        cache_key = f"static_vectorized_{hash(tuple(symbols))}_{hash(tuple(expressions))}_{logic}"
        cached_result = self.cache.get(cache_key)
        if cached_result is not None:
            return cached_result

        try:
            # Get metadata DataFrame for all symbols
            metadata_df = self.metadata_provider.get_metadata_dataframe(symbols)

            # Filter to only requested symbols that exist in metadata
            available_symbols = [s for s in symbols if s in metadata_df.index]
            if not available_symbols:
                self.cache.set(cache_key, [])
                return []

            metadata_df = metadata_df.loc[available_symbols]

            # Evaluate each condition as a boolean Series
            condition_results = []

            for expression in expressions:
                try:
                    # Create safe environment with metadata columns as variables
                    safe_env = {
                        "__builtins__": {},
                        # Add all metadata columns as series for vectorized operations
                        **{col: metadata_df[col] for col in metadata_df.columns},
                        "pd": pd,
                    }

                    # Evaluate expression - should return a boolean Series
                    result = eval(expression, safe_env)

                    # Ensure result is a boolean Series
                    if isinstance(result, pd.Series):
                        condition_results.append(result.astype(bool))
                    else:
                        # If scalar, broadcast to all symbols
                        condition_results.append(pd.Series([bool(result)] * len(metadata_df), index=metadata_df.index))

                except Exception as e:
                    logger.debug(f"Static condition '{expression}' failed: {e}")
                    # Add False series for failed condition
                    condition_results.append(pd.Series([False] * len(metadata_df), index=metadata_df.index))

            if not condition_results:
                selected_symbols = available_symbols
            else:
                # Combine results based on logic
                if logic == "and":
                    # All conditions must be True
                    combined = condition_results[0]
                    for cond in condition_results[1:]:
                        combined = combined & cond
                else:  # "or"
                    # At least one condition must be True
                    combined = condition_results[0]
                    for cond in condition_results[1:]:
                        combined = combined | cond

                # Get symbols where condition is True
                selected_symbols = combined[combined].index.tolist()

            self.cache.set(cache_key, selected_symbols)
            return selected_symbols

        except Exception as e:
            logger.error(f"Vectorized static condition evaluation failed: {e}")
            self.cache.set(cache_key, [])
            return []

    def _evaluate_expression(self, symbol: str, df: pd.DataFrame, expression: str) -> Any:
        """
        Internal method to evaluate expression against DataFrame.

        Args:
            symbol: Symbol identifier
            df: OHLCV DataFrame
            expression: Expression to evaluate

        Returns:
            Any: Result of expression evaluation
        """
        # Create local environment with OHLCV data and technical indicators
        local_env = {
            # OHLCV data
            "c": df["close"],
            "o": df["open"],
            "h": df["high"],
            "l": df["low"],
            "v": df["volume"],

            # Technical indicators
            "sma": sma_single,
            "ema": ema_single,
            "min": min_single,
            "max": max_single,
            "count": count_single,
            "countTrue": count_true_single,
            "prv": prv_single,
        }

        # Add metadata if available
        if self.metadata_provider:
            try:
                metadata = self.metadata_provider.get_all_metadata(symbol)
                # Add metadata as scalar values that can be used in expressions
                local_env.update(metadata)
            except Exception as e:
                logger.debug(f"Failed to load metadata for {symbol}: {e}")

        # Evaluate expression in safe environment
        return eval(expression, {"__builtins__": {}}, local_env)

    def reduce_condition_by_period(self, bool_series: pd.Series, mode: Literal["now", "x_bar_ago", "within_last", "in_row"] | None, value: int | None) -> bool:
        """
        Reduce boolean series to single boolean based on evaluation period.

        Args:
            bool_series: Boolean series from condition evaluation
            mode: Evaluation mode ('now', 'x_bar_ago', 'within_last', 'in_row')
            value: Period value (required for some modes)

        Returns:
            bool: Final condition result
        """
        if len(bool_series) == 0:
            return False

        if mode == "now":
            return bool(bool_series.iloc[-1])

        elif mode == "x_bar_ago":
            if len(bool_series) < value:
                return False
            return bool(bool_series.iloc[-value])

        elif mode == "within_last":
            last_n = bool_series.tail(value)
            return bool(last_n.any())

        elif mode == "in_row":
            if len(bool_series) < value:
                return False
            last_n = bool_series.tail(value)
            return bool(last_n.all())

        return False

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache performance statistics."""
        return self.cache.get_stats()

    def clear_cache(self) -> None:
        """Clear expression cache."""
        self.cache.clear()
