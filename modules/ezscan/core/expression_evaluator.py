"""
Expression evaluation engine for technical analysis.

Handles the evaluation of technical expressions against symbol data
with caching for performance optimization.
"""

import logging
from typing import Dict, Any
import pandas as pd

from modules.ezscan.core.technical_indicators import (
    sma_single, ema_single, prv_single, min_single, max_single,
    count_single, count_true_single
)
from modules.ezscan.utils.cache import ExpressionCache

logger = logging.getLogger(__name__)


class ExpressionEvaluator:
    """
    Evaluates technical expressions against symbol OHLCV data.

    This class handles both value expressions (returning a single value)
    and condition expressions (returning boolean series for period evaluation).
    """

    def __init__(self, cache_enabled: bool = True):
        """Initialize the expression evaluator with cache."""
        self.cache = ExpressionCache(enabled=cache_enabled)

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
            result = self._evaluate_expression(df, expression)

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
            result = self._evaluate_expression(df, expression)

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

    def _evaluate_expression(self, df: pd.DataFrame, expression: str) -> Any:
        """
        Internal method to evaluate expression against DataFrame.

        Args:
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

        # Evaluate expression in safe environment
        return eval(expression, {"__builtins__": {}}, local_env)

    def reduce_condition_by_period(self, bool_series: pd.Series, mode: str, value: int | None) -> bool:
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
