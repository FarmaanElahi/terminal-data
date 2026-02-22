import logging
from typing import Any

import numpy as np
import pandas as pd

from terminal.market_feed.manager import MarketDataManager
from terminal.scan.formula import FormulaError, evaluate, parse
from terminal.scan.models import ColumnDef, ConditionParam, Scan

logger = logging.getLogger(__name__)


def evaluate_condition(df: pd.DataFrame, condition: ConditionParam) -> np.ndarray:
    """
    Evaluates a single condition against the OHLCV DataFrame and returns a boolean history array.
    """
    try:
        result = evaluate_expression(df, condition.formula)

        # Ensure boolean array
        if result.dtype != bool:
            bool_result = np.zeros(len(df), dtype=bool)
            if isinstance(result, np.ndarray):
                valid = ~np.isnan(result.astype(float, copy=False))
                bool_result[valid] = result[valid].astype(bool)
            return bool_result
        return result

    except FormulaError as e:
        logger.warning(f"Formula error in '{condition.formula}': {e.message}")
        return np.zeros(len(df), dtype=bool)
    except Exception as e:
        logger.warning(f"Failed to evaluate condition '{condition.formula}': {e}")
        return np.zeros(len(df), dtype=bool)


def evaluate_expression(df: pd.DataFrame, expression: str) -> np.ndarray:
    """
    Evaluates a formula expression and returns the result array (float64 or bool).
    Used for column value computation.
    """
    ast = parse(expression)
    return evaluate(ast, df)


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
    scan: Scan, symbols: list[str], market_manager: MarketDataManager
) -> dict[str, Any]:
    """
    Executes the scan across the given symbols.
    Returns a dictionary contains columns and rows matching the columns.
    """
    values = []
    tickers = []

    # Columns definition
    column_ids = []
    col_definitions: list[ColumnDef] = []
    for raw_col in scan.columns:
        col_def = ColumnDef(**raw_col) if isinstance(raw_col, dict) else raw_col
        column_ids.append(col_def.id)
        col_definitions.append(col_def)

    condition_tf = "D"

    # Pre-parse condition formulas (cacheable ASTs)
    parsed_conditions: list[tuple[ConditionParam, object | None]] = []
    if scan.conditions:
        for raw_cond in scan.conditions:
            cond = (
                ConditionParam(**raw_cond) if isinstance(raw_cond, dict) else raw_cond
            )
            try:
                ast = parse(cond.formula)
                parsed_conditions.append((cond, ast))
            except FormulaError as e:
                logger.warning(f"Formula parse error: {e.message}")
                parsed_conditions.append((cond, None))

    # Pre-parse column expressions
    parsed_columns: list[tuple[ColumnDef, object | None]] = []
    for col_def in col_definitions:
        if col_def.type == "value" and col_def.expression:
            try:
                ast = parse(col_def.expression)
                parsed_columns.append((col_def, ast))
            except FormulaError as e:
                logger.warning(f"Column expression parse error: {e.message}")
                parsed_columns.append((col_def, None))
        else:
            parsed_columns.append((col_def, None))

    for symbol in symbols[:2200]:
        df = market_manager.get_ohlcv(symbol, timeframe=condition_tf)
        if df is None or len(df) == 0:
            continue

        # 1. Evaluate Conditions
        passes_scan = True

        if parsed_conditions:
            condition_results = []
            for cond, ast in parsed_conditions:
                if ast is None:
                    condition_results.append(False)
                    continue
                try:
                    bool_arr = evaluate(ast, df)
                    if bool_arr.dtype != bool:
                        tmp = np.zeros(len(df), dtype=bool)
                        if isinstance(bool_arr, np.ndarray):
                            valid = ~np.isnan(bool_arr.astype(float, copy=False))
                            tmp[valid] = bool_arr[valid].astype(bool)
                        bool_arr = tmp
                    met = is_condition_met(bool_arr, cond)
                except Exception as e:
                    logger.warning(
                        f"Failed to evaluate condition '{cond.formula}' for {symbol}: {e}"
                    )
                    met = False
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

        for col_def, col_ast in parsed_columns:
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
                if col_def.type == "value" and col_ast is not None:
                    res_arr = evaluate(col_ast, col_df)
                    res_arr = np.asarray(res_arr)

                    if col_def.bar_ago:
                        idx = -(col_def.bar_ago + 1)
                        val = res_arr[idx] if len(res_arr) >= abs(idx) else None
                    else:
                        val = res_arr[-1] if len(res_arr) > 0 else None

                    # Convert numpy types to python native types for JSON serialization
                    if val is not None:
                        if isinstance(val, (np.integer, np.floating)):
                            val = val.item()
                        elif isinstance(val, np.bool_):
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
