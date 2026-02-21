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
) -> Dict[str, Any]:
    """
    Executes the scan across the given symbols.
    Returns a dictionary contains columns and rows matching the columns.
    """
    values = []
    tickers = []

    # Columns definition
    # We use scan.columns to determine the list of extra columns.
    # The first column is always 'symbol'
    column_ids = []
    col_definitions: List[ColumnDef] = []
    for raw_col in scan.columns:
        col_def = ColumnDef(**raw_col) if isinstance(raw_col, dict) else raw_col
        column_ids.append(col_def.id)
        col_definitions.append(col_def)

    # 1. Evaluate Conditions (Foundational evaluate)
    # Usually, a single scan applies conditions to a specific timeframe, or we use the base one.
    # The user requirements didn't specify condition-level timeframe, only column-level timeframe.
    # But an implicit assumption is conditions might be meant for the same timeframe.
    # To be safe, we will just use timeframe="D" for the foundational evaluation of conditions,
    # unless conditions themselves gain a timeframe attribute later.
    condition_tf = "D"

    for symbol in symbols:
        df = market_manager.get_ohlcv(symbol, timeframe=condition_tf)
        if df is None or len(df) == 0:
            continue

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
        row = []

        for col_def in col_definitions:
            # We must fetch data for the specific column's timeframe
            col_tf = col_def.timeframe or "D"
            if col_tf == condition_tf:
                col_df = df
            else:
                col_df = market_manager.get_ohlcv(symbol, timeframe=col_tf)
                if col_df is None or len(col_df) == 0:
                    row.append(None)
                    continue

            try:
                if col_def.type == "value" and col_def.expression:
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

                    row.append(val)
                else:
                    row.append(None)

            except Exception as e:
                logger.warning(f"Failed to evaluate column '{col_def.expression}': {e}")
                row.append(None)

        tickers.append(symbol)
        values.append(row)

    return {
        "total": len(values),
        "columns": column_ids,
        "tickers": tickers,
        "values": values,
    }
