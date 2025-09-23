import logging
from typing import Dict, Any, Optional, List, Literal
import pandas as pd
import numpy as np

from modules.ezscan.core.technical_indicators import (
    sma_single, ema_single, prv_single, min_single, max_single,
    count_single, count_true_single, change
)
from modules.ezscan.interfaces.metadata_provider import MetadataProvider
from modules.ezscan.utils.cache import ExpressionCache

logger = logging.getLogger(__name__)


class ExpressionEvaluator:
    """Evaluates technical expressions against symbol OHLCV data with caching."""

    def __init__(self, cache_enabled: bool = True, metadata_provider: Optional[MetadataProvider] = None):
        """Initialize evaluator with cache."""
        self.cache = ExpressionCache(enabled=cache_enabled)
        self.metadata_provider = metadata_provider

    def evaluate_value_expression(self, symbol: str, df: pd.DataFrame, expression: str) -> Optional[float]:
        """Evaluate expression and return the last value."""
        cache_key = f"{symbol}_val_{hash(expression)}"

        if cached_result := self.cache.get(cache_key):
            return cached_result

        try:
            result = self._evaluate_expression(symbol, df, expression)
            if isinstance(result, pd.Series) and not result.empty:
                last_val = result.iloc[-1]
            elif np.isscalar(result) and not pd.isna(result):
                if isinstance(result, (int, np.integer)):
                    last_val = int(result)
                elif isinstance(result, (float, np.floating)):
                    last_val = float(result)
                else:
                    last_val = result  # Keep other scalar types as-is
            else:
                last_val = None
            last_val = None if pd.isna(last_val) else last_val

            self.cache.set(cache_key, last_val)
            return last_val

        except Exception as e:
            logger.error(f"Expression '{expression}' failed for {symbol}: {e}", exc_info=True)
            self.cache.set(cache_key, None)
            return None

    def evaluate_condition_expression(self, symbol: str, df: pd.DataFrame, expression: str) -> pd.Series:
        """Evaluate condition expression and return boolean series."""
        cache_key = f"{symbol}_cond_{hash(expression)}"

        if cached_result := self.cache.get(cache_key):
            return cached_result

        try:
            result = self._evaluate_expression(symbol, df, expression)
            bool_series = result.astype(bool) if isinstance(result, pd.Series) else pd.Series(
                [bool(result)] * len(df), index=df.index, dtype=bool
            )

            self.cache.set(cache_key, bool_series)
            return bool_series

        except Exception as e:
            logger.error(f"Condition '{expression}' failed for {symbol}: {e}", exc_info=True)
            false_series = pd.Series(False, index=df.index, dtype=bool)
            self.cache.set(cache_key, false_series)
            return false_series

    def evaluate_rank_condition(self, symbol: str, expression: str, all_symbol_data: Dict[str, pd.DataFrame],
                                rank_min: int = 1, rank_max: int = 99) -> bool:
        """Evaluate rank-based condition by comparing symbol's rank against all symbols."""
        cache_key = f"rank_{hash(expression)}_{rank_min}_{rank_max}_{hash(tuple(sorted(all_symbol_data.keys())))}"

        if cached_result := self.cache.get(cache_key):
            symbol_ranks = cached_result
        else:
            # Calculate expression values for all symbols
            symbol_values = {}
            for sym, df in all_symbol_data.items():
                try:
                    value = self.evaluate_value_expression(sym, df, expression)
                    if value is not None and not pd.isna(value):
                        symbol_values[sym] = float(value)
                except Exception as e:
                    logger.debug(f"Failed to evaluate expression for {sym}: {e}")
                    continue

            if len(symbol_values) < 2:
                logger.warning("Not enough symbols with valid values for ranking")
                return False

            # Calculate percentile ranks (0-100)
            values_series = pd.Series(symbol_values)
            ranks = values_series.rank(method='min', pct=True) * 100
            symbol_ranks = ranks.to_dict()

            self.cache.set(cache_key, symbol_ranks)

        # Check if this symbol's rank is within the specified range
        symbol_rank = symbol_ranks.get(symbol)
        if symbol_rank is None:
            return False

        return rank_min <= symbol_rank <= rank_max

    def evaluate_rank_conditions_vectorized(self, symbols: List[str], expressions: List[str],
                                            rank_mins: List[int], rank_maxes: List[int],
                                            all_symbol_data: Dict[str, pd.DataFrame],
                                            logic: Literal["and", "or"] = "and") -> List[str]:
        """Evaluate rank conditions for multiple expressions vectorized."""
        if not expressions:
            return symbols

        cache_key = f"rank_vectorized_{hash(tuple(expressions))}_{hash(tuple(rank_mins))}_{hash(tuple(rank_maxes))}_{logic}_{hash(tuple(sorted(all_symbol_data.keys())))}"

        if cached_result := self.cache.get(cache_key):
            return cached_result

        try:
            condition_results = []

            for expression, rank_min, rank_max in zip(expressions, rank_mins, rank_maxes):
                # Calculate expression values for all symbols
                symbol_values = {}
                for sym in all_symbol_data.keys():
                    try:
                        value = self.evaluate_value_expression(sym, all_symbol_data[sym], expression)
                        if value is not None and not pd.isna(value):
                            symbol_values[sym] = float(value)
                    except Exception as e:
                        logger.debug(f"Failed to evaluate expression for {sym}: {e}")
                        continue

                if len(symbol_values) < 2:
                    logger.warning(f"Not enough symbols with valid values for ranking expression: {expression}")
                    condition_results.append(pd.Series(False, index=symbols))
                    continue

                # Calculate percentile ranks
                values_series = pd.Series(symbol_values)
                ranks = values_series.rank(method='min', pct=True) * 100

                # Create boolean series for symbols that meet rank criteria
                symbol_meets_rank = {}
                for sym in symbols:
                    rank = ranks.get(sym)
                    symbol_meets_rank[sym] = (rank is not None and rank_min <= rank <= rank_max)

                condition_results.append(pd.Series(symbol_meets_rank))

            # Combine conditions with logic
            if len(condition_results) == 1:
                combined = condition_results[0]
            else:
                combined = condition_results[0]
                for cond in condition_results[1:]:
                    combined = combined & cond if logic == "and" else combined | cond

            selected_symbols = combined[combined].index.tolist()

            self.cache.set(cache_key, selected_symbols)
            return selected_symbols

        except Exception as e:
            logger.error(f"Vectorized rank condition evaluation failed: {e}", exc_info=True)
            self.cache.set(cache_key, [])
            return []

    def evaluate_static_conditions_vectorized(self, symbols: List[str], expressions: List[str], logic: Literal["and", "or"] = "and") -> List[str]:
        """Evaluate static conditions vectorized."""
        if not expressions or not self.metadata_provider:
            return symbols

        cache_key = f"static_vectorized_{hash(tuple(symbols))}_{hash(tuple(expressions))}_{logic}"

        if cached_result := self.cache.get(cache_key):
            return cached_result

        try:
            metadata_df = self.metadata_provider.get_metadata_dataframe(symbols)
            available_symbols = [s for s in symbols if s in metadata_df.index]

            if not available_symbols:
                self.cache.set(cache_key, [])
                return []

            metadata_df = metadata_df.loc[available_symbols]
            condition_results = []

            for expression in expressions:
                safe_env = {
                    "__builtins__": {},
                    **{col: metadata_df[col] for col in metadata_df.columns},
                    "pd": pd,
                    "np": np
                }
                result = eval(expression, safe_env)
                condition_results.append(result.astype(bool) if isinstance(result, pd.Series) else
                                         pd.Series([bool(result)] * len(metadata_df), index=metadata_df.index))

            combined = condition_results[0]
            for cond in condition_results[1:]:
                combined = combined & cond if logic == "and" else combined | cond

            selected_symbols = combined[combined].index.tolist()

            self.cache.set(cache_key, selected_symbols)
            return selected_symbols

        except Exception as e:
            logger.error(f"Vectorized static condition evaluation failed: {e}", exc_info=True)
            self.cache.set(cache_key, [])
            return []

    def evaluate_condition_column(self, symbol: str, df: pd.DataFrame, conditions: List['Condition'],
                                  logic: Literal["and", "or"] = "and",
                                  all_symbol_data: Optional[Dict[str, pd.DataFrame]] = None) -> bool:
        """Evaluate multiple conditions for a condition column."""
        cache_key = f"{symbol}_condcol_{hash(tuple((c.expression, c.condition_type, c.evaluation_period, c.evaluation_type, c.value, c.rank_min, c.rank_max) for c in conditions))}_{logic}"

        if cached_result := self.cache.get(cache_key):
            return cached_result

        try:
            condition_results = []

            for condition in conditions:
                if condition.condition_type == "static" and self.metadata_provider:
                    metadata = self.metadata_provider.get_all_metadata(symbol)
                    safe_env = {"__builtins__": {}, **metadata}
                    result = eval(condition.expression, safe_env)
                    condition_results.append(bool(result))
                elif condition.evaluation_type == "rank":
                    if all_symbol_data is None:
                        logger.error("all_symbol_data required for rank evaluation")
                        condition_results.append(False)
                    else:
                        result = self.evaluate_rank_condition(
                            symbol, condition.expression, all_symbol_data,
                            condition.rank_min or 1, condition.rank_max or 99
                        )
                        condition_results.append(result)
                else:
                    # Boolean evaluation (existing logic)
                    bool_series = self.evaluate_condition_expression(symbol, df, condition.expression)
                    result = self.reduce_condition_by_period(bool_series, condition.evaluation_period, condition.value)
                    condition_results.append(result)

            final_result = all(condition_results) if logic == "and" else any(condition_results)

            self.cache.set(cache_key, final_result)
            return final_result

        except Exception as e:
            logger.error(f"Condition column evaluation failed for {symbol}: {e}", exc_info=True)
            self.cache.set(cache_key, False)
            return False

    def _evaluate_expression(self, symbol: str, df: pd.DataFrame, expression: str) -> Any:
        """Internal method to evaluate expression."""
        local_env = {
            "c": df["close"], "o": df["open"], "h": df["high"], "l": df["low"],
            "v": df["volume"], "i": df.index,
            "sma": sma_single, "ema": ema_single, "min": min_single, "max": max_single,
            "count": count_single, "countTrue": count_true_single, "prv": prv_single, "change": change,
            "pd": pd, "np": np
        }

        if self.metadata_provider:
            try:
                metadata = self.metadata_provider.get_all_metadata(symbol)
                local_env.update(metadata)
            except Exception as e:
                logger.debug(f"Failed to load metadata for {symbol}: {e}")

        return eval(expression, {"__builtins__": {}}, local_env)

    def reduce_condition_by_period(self, bool_series: pd.Series, mode: Optional[Literal["now", "x_bar_ago", "within_last", "in_row"]],
                                   value: Optional[int]) -> bool:
        """Reduce boolean series to single boolean based on evaluation period."""
        if bool_series.empty:
            return False

        if mode == "now":
            return bool(bool_series.iloc[-1])
        elif mode == "x_bar_ago" and value:
            return bool(bool_series.iloc[-value]) if len(bool_series) >= value else False
        elif mode == "within_last" and value:
            return bool(bool_series.tail(value).any())
        elif mode == "in_row" and value:
            return bool(bool_series.tail(value).all()) if len(bool_series) >= value else False
        return False

    def enable_cache(self) -> None:
        """Enable caching."""
        self.cache.enabled = True

    def disable_cache(self) -> None:
        """Disable caching."""
        self.cache.enabled = False

    def is_cache_enabled(self) -> bool:
        """Check if caching is enabled."""
        return self.cache.enabled

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache performance statistics."""
        return self.cache.get_stats()

    def clear_cache(self) -> None:
        """Clear expression cache."""
        self.cache.clear()