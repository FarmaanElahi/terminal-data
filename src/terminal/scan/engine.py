import logging
from typing import Any, Dict, List

import numpy as np
import pandas as pd

from terminal.market_feed.manager import MarketDataManager
from terminal.scan.models import ConditionParam, ColumnDef, Scan

logger = logging.getLogger(__name__)


def evaluate_condition(df: pd.DataFrame, condition: ConditionParam) -> np.ndarray:
    """
    Evaluates a single condition against the OHLCV DataFrame and returns a boolean history array.
    """
    try:
        # Assign short-hand variables directly to the DataFrame
        df["O"] = df["open"]
        df["H"] = df["high"]
        df["L"] = df["low"]
        df["C"] = df["close"]
        df["V"] = df["volume"]

        # We need engine="python" to support more complex logic
        result_series = df.eval(condition.formula, engine="python")

        # Convert to boolean numpy array
        return result_series.to_numpy(dtype=bool)
    except Exception as e:
        logger.warning(f"Failed to evaluate condition '{condition.formula}': {e}")
        return np.zeros(len(df), dtype=bool)


def is_condition_met(bool_array: np.ndarray, condition: ConditionParam) -> bool:
    """
    Processes the raw boolean array based on the `true_when` parameter.
    """
    if len(bool_array) == 0:
        return False

    if condition.true_when == "now":
        # Must be true on the very final candle
        return bool(bool_array[-1])

    elif condition.true_when == "x_bar_ago":
        # e.g., if true_when_param = 1, it means the bar before the current one
        # index -1 is 'now', index -2 is '1 bar ago', etc.
        param = condition.true_when_param or 1
        idx = -(param + 1)
        if len(bool_array) >= abs(idx):
            return bool(bool_array[idx])
        return False

    elif condition.true_when == "within_last":
        # True if it occurred anytime within the last N bars
        param = condition.true_when_param or 5
        # Don't slice more than we have
        slice_idx = max(0, len(bool_array) - param)
        return bool(np.any(bool_array[slice_idx:]))

    return False


def run_scan_engine(
    scan: Scan, symbols: List[str], market_manager: MarketDataManager
) -> List[Dict[str, Any]]:
    """
    Executes the scan across the given symbols.
    Returns a list of matching symbols along with their requested column values.
    """
    results = []

    # Map timeframes needed by conditions so we don't fetch D multiple times if they all want W
    # Usually, a single scan applies conditions to a specific timeframe, or we use the base one.
    # The user requirements didn't specify condition-level timeframe, only column-level timeframe.
    # But an implicit assumption is conditions might be meant for the same timeframe.
    # To be safe, we will just use timeframe="D" for the foundational evaluation of conditions,
    # unless conditions themselves gain a timeframe attribute later.
    # Let's assess the columns. We can extract their requested timeframes.

    # We will assume condition evaluation happens on the daily timeframe by default,
    # since ConditionParam lacks a `timeframe` field.
    condition_tf = "D"

    for symbol in symbols:
        data = market_manager.get_ohlcv(symbol, timeframe=condition_tf)
        if not data or len(data["close"]) == 0:
            continue

        df = pd.DataFrame(data)

        # 1. Evaluate Conditions
        passes_scan = True

        if scan.conditions:
            condition_results = []
            for raw_cond in scan.conditions:
                cond = (
                    ConditionParam(**raw_cond)
                    if isinstance(raw_cond, dict)
                    else raw_cond
                )
                bool_arr = evaluate_condition(df, cond)
                met = is_condition_met(bool_arr, cond)
                condition_results.append(met)

            if scan.conditional_logic == "and":
                passes_scan = all(condition_results)
            elif scan.conditional_logic == "or":
                passes_scan = any(condition_results)

        # If it doesn't pass, move on
        if not passes_scan:
            continue

        # 2. It passed! Build the result row
        row = {"symbol": symbol}

        for raw_col in scan.columns:
            col_def = ColumnDef(**raw_col) if isinstance(raw_col, dict) else raw_col
            # We must fetch data for the specific column's timeframe
            col_tf = col_def.timeframe or "D"
            if col_tf == condition_tf:
                col_data = data
                col_df = df
            else:
                col_data = market_manager.get_ohlcv(symbol, timeframe=col_tf)
                if not col_data or len(col_data["close"]) == 0:
                    row[col_def.id] = None
                    continue
                col_df = pd.DataFrame(col_data)

            try:
                if col_def.type == "value" and col_def.expression:
                    col_df["O"] = col_df["open"]
                    col_df["H"] = col_df["high"]
                    col_df["L"] = col_df["low"]
                    col_df["C"] = col_df["close"]
                    col_df["V"] = col_df["volume"]

                    res_series = col_df.eval(col_def.expression, engine="python")
                    res_arr = res_series.to_numpy()

                    if col_def.bar_ago:
                        idx = -(col_def.bar_ago + 1)
                        val = res_arr[idx] if len(res_arr) >= abs(idx) else None
                    else:
                        val = res_arr[-1] if len(res_arr) > 0 else None

                    # Convert numpy types to python native types for JSON serialization
                    if val is not None:
                        if isinstance(val, (np.integer, np.floating)):
                            val = val.item()
                        elif isinstance(val, (np.bool_)):
                            val = bool(val)

                    row[col_def.id] = val

            except Exception as e:
                logger.warning(f"Failed to evaluate column '{col_def.expression}': {e}")
                row[col_def.id] = None

        results.append(row)

    return results
