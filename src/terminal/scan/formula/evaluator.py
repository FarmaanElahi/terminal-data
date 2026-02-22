"""Tree-walking evaluator — AST × DataFrame → NumPy array.

Every operation maps to a vectorised NumPy/pandas call.
No Python-level row iteration whatsoever.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from terminal.scan.formula.ast_nodes import (
    BinOp,
    FieldRef,
    FuncCall,
    Node,
    NumberLiteral,
    ShiftExpr,
    UnaryOp,
)
from terminal.scan.formula.errors import FormulaError
from terminal.scan.formula.functions import get_func

# Map canonical field names to DataFrame column names.
_COL_MAP: dict[str, str] = {
    "C": "close",
    "O": "open",
    "H": "high",
    "L": "low",
    "V": "volume",
}

# NumPy ops for binary operators
_ARITH_OPS: dict[str, np.ufunc] = {
    "+": np.add,
    "-": np.subtract,
    "*": np.multiply,
    "/": np.divide,
}

_CMP_OPS: dict[str, np.ufunc] = {
    ">": np.greater,
    "<": np.less,
    ">=": np.greater_equal,
    "<=": np.less_equal,
    "==": np.equal,
    "!=": np.not_equal,
}

_BOOL_OPS: dict[str, np.ufunc] = {
    "AND": np.logical_and,
    "OR": np.logical_or,
}


def evaluate(node: Node, df: pd.DataFrame) -> np.ndarray:
    """Evaluate *node* against *df* and return a NumPy array.

    The result is either ``float64`` (arithmetic / function) or ``bool``
    (comparison / boolean), with the same length as ``len(df)``.
    """
    return _eval(node, df)


def _eval(node: Node, df: pd.DataFrame) -> np.ndarray:
    """Recursively evaluate an AST node."""

    if isinstance(node, NumberLiteral):
        # Broadcast scalar to full array length for consistency,
        # but we can also just return the scalar and let NumPy handle it.
        # Returning a scalar is fine — NumPy broadcast rules apply.
        return np.float64(node.value)

    if isinstance(node, FieldRef):
        col = _COL_MAP.get(node.name)
        if col is None or col not in df.columns:
            raise FormulaError(
                f'Cannot resolve field "{node.name}" to a DataFrame column'
            )
        return df[col].to_numpy(dtype=np.float64)

    if isinstance(node, ShiftExpr):
        inner = _eval_as_series(node.expr, df)
        return inner.shift(node.periods).to_numpy(dtype=np.float64)

    if isinstance(node, UnaryOp):
        operand = _eval(node.operand, df)
        if node.op == "-":
            return np.negative(operand)
        if node.op == "NOT":
            return np.logical_not(_to_bool(operand))
        raise FormulaError(f"Unknown unary operator: {node.op}")

    if isinstance(node, BinOp):
        left = _eval(node.left, df)
        right = _eval(node.right, df)

        if node.op in _ARITH_OPS:
            with np.errstate(divide="ignore", invalid="ignore"):
                return _ARITH_OPS[node.op](
                    np.asarray(left, dtype=np.float64),
                    np.asarray(right, dtype=np.float64),
                )

        if node.op in _CMP_OPS:
            return _CMP_OPS[node.op](
                np.asarray(left, dtype=np.float64),
                np.asarray(right, dtype=np.float64),
            )

        if node.op in _BOOL_OPS:
            return _BOOL_OPS[node.op](_to_bool(left), _to_bool(right))

        raise FormulaError(f"Unknown binary operator: {node.op}")

    if isinstance(node, FuncCall):
        func_def = get_func(node.name)
        # First arg is the source (an array), remaining are numeric params.
        evaluated_args: list[np.ndarray | float] = []
        for i, arg in enumerate(node.args):
            val = _eval(arg, df)
            if i == 0:
                # Source must be a full array
                evaluated_args.append(np.asarray(val, dtype=np.float64))
            else:
                # Numeric params — extract scalar
                if isinstance(val, np.ndarray):
                    if val.ndim == 0:
                        evaluated_args.append(float(val))
                    else:
                        # Non-scalar as parameter — use last value
                        evaluated_args.append(float(val[-1]))
                else:
                    evaluated_args.append(float(val))
        return func_def.impl(*evaluated_args)

    raise FormulaError(f"Unknown AST node type: {type(node).__name__}")


def _eval_as_series(node: Node, df: pd.DataFrame) -> pd.Series:
    """Evaluate *node* and return a pandas Series (for shift support)."""
    if isinstance(node, FieldRef):
        col = _COL_MAP.get(node.name)
        if col is None or col not in df.columns:
            raise FormulaError(
                f'Cannot resolve field "{node.name}" to a DataFrame column'
            )
        return df[col].copy()

    # For complex sub-expressions, wrap the numpy result in a Series
    arr = _eval(node, df)
    return pd.Series(np.asarray(arr, dtype=np.float64), index=df.index)


def _to_bool(arr: np.ndarray | np.floating) -> np.ndarray:
    """Convert to boolean array, treating NaN as False."""
    arr = np.asarray(arr)
    if arr.dtype == bool:
        return arr
    # For float arrays, NaN → False
    result = np.zeros_like(arr, dtype=bool)
    valid = (
        ~np.isnan(arr.astype(float, copy=False))
        if np.issubdtype(arr.dtype, np.floating)
        else np.ones_like(arr, dtype=bool)
    )
    result[valid] = arr[valid].astype(bool)
    return result
