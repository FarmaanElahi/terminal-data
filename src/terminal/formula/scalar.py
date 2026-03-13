"""Zero-allocation scalar evaluation for simple formula ASTs.

For formulas that contain only arithmetic/comparisons on OHLCV field references
(``C``, ``O``, ``H``, ``L``, ``V``), bar-shifts (``C.1``, ``H.5``), and common
window functions (``SMA``, ``EMA``, ``MIN``/``LOWEST``, ``MAX``/``HIGHEST``), the
result at the last bar can be computed directly from the raw numpy arrays
stored in ``OHLCStore`` — with **no pandas DataFrame allocation at all**.

This is used as the inner fast-path in the screener column and condition evaluator.
Formulas that reference unsupported functions (``RSI``, ``RMV``, ``VWAP``, …) or
nested shifts fall back to the standard ``evaluate()`` path.

Usage
-----
>>> from terminal.formula import parse
>>> from terminal.formula.scalar import scalar_last
>>> import numpy as np
>>> ohlcv = np.array([[100., 105., 99., 104., 1000.],
...                   [104., 108., 103., 107., 2000.]], dtype='float32')
>>> ast = parse('(C - C.1) / C.1 * 100')
>>> scalar_last(ast, ohlcv, size=2)
2.884...
"""

from __future__ import annotations

import math

import numpy as np

from .ast_nodes import BinOp, FieldRef, FuncCall, Node, NumberLiteral, ShiftExpr, UnaryOp

# Maps canonical short field names (and long names) to column index in ohlcv array.
# Column order: open=0  high=1  low=2  close=3  volume=4
_FIELD_IDX: dict[str, int] = {
    "O": 0, "H": 1, "L": 2, "C": 3, "V": 4,
    "OPEN": 0, "HIGH": 1, "LOW": 2, "CLOSE": 3, "VOLUME": 4,
}

# Sentinel raised (not returned) when the AST cannot be evaluated in scalar mode.
# Using an exception is cleaner than propagating a nullable sentinel through every
# recursive call when the common path never raises.
class _Unsupported(Exception):
    """Raised when the AST contains a node that requires the full evaluate() path."""


def scalar_last(node: Node, ohlcv: np.ndarray, size: int) -> float | None:
    """Evaluate *node* at the last bar, reading directly from the numpy buffer.

    Parameters
    ----------
    node:
        Parsed formula AST.
    ohlcv:
        Shape ``(capacity, 5)`` float32 array as stored in ``OHLCStore``.
        Column order: open, high, low, close, volume.
    size:
        Number of valid rows (``OHLCStore._sizes[key]``).

    Returns
    -------
    float or None
        The scalar value at ``result[-1]``, or ``None`` when the formula
        references window functions or out-of-range history.

    Raises ``_Unsupported`` when the AST cannot be evaluated without a full
    DataFrame — callers should catch this and fall back to ``evaluate()``.
    """
    if size == 0:
        return None
    try:
        val = _eval(node, ohlcv, size)
        if val is None or math.isnan(val) or math.isinf(val):
            return None
        return float(val)
    except _Unsupported:
        raise  # let the caller fall back
    except (ZeroDivisionError, OverflowError, FloatingPointError):
        return None


def can_scalar_eval(node: Node) -> bool:
    """Return True if *node* can be evaluated by ``scalar_last`` without a DataFrame."""
    try:
        _check(node)
        return True
    except _Unsupported:
        return False


# ---------------------------------------------------------------------------
# Internal recursive evaluator
# ---------------------------------------------------------------------------


def _eval(node: Node, ohlcv: np.ndarray, size: int) -> float | None:
    if isinstance(node, NumberLiteral):
        return node.value

    if isinstance(node, FieldRef):
        idx = _FIELD_IDX.get(node.name.upper())
        if idx is None:
            raise _Unsupported(f"unknown field {node.name!r}")
        return float(ohlcv[size - 1, idx])

    if isinstance(node, ShiftExpr):
        # Only supports FieldRef at the inner node — nested shifts would need
        # window-aware evaluation.
        inner = node.expr
        if not isinstance(inner, FieldRef):
            raise _Unsupported("nested shift")
        idx = _FIELD_IDX.get(inner.name.upper())
        if idx is None:
            raise _Unsupported(f"unknown field {inner.name!r}")
        pos = size - 1 - node.periods
        if pos < 0:
            return None  # not enough history (treat as NaN)
        return float(ohlcv[pos, idx])

    if isinstance(node, UnaryOp):
        val = _eval(node.operand, ohlcv, size)
        if val is None:
            return None
        if node.op == "-":
            return -val
        if node.op == "NOT":
            return float(not val)
        raise _Unsupported(f"unknown unary op {node.op!r}")

    if isinstance(node, BinOp):
        left = _eval(node.left, ohlcv, size)
        right = _eval(node.right, ohlcv, size)
        if left is None or right is None:
            return None
        op = node.op
        if op == "+":
            return left + right
        if op == "-":
            return left - right
        if op == "*":
            return left * right
        if op == "/":
            if right == 0:
                return None
            return left / right
        if op == "**":
            return left ** right
        if op == ">":
            return float(left > right)
        if op == "<":
            return float(left < right)
        if op == ">=":
            return float(left >= right)
        if op == "<=":
            return float(left <= right)
        if op == "==":
            return float(left == right)
        if op == "!=":
            return float(left != right)
        if op == "AND":
            return float(bool(left) and bool(right))
        if op == "OR":
            return float(bool(left) or bool(right))
        raise _Unsupported(f"unknown binary op {op!r}")

    if isinstance(node, FuncCall):
        name = node.name
        args = node.args

        if name in ("SMA", "MIN", "LOWEST", "MAX", "HIGHEST", "EMA") and len(args) == 2:
            src, period_node = args
            if not isinstance(period_node, NumberLiteral):
                raise _Unsupported("non-literal period")
            period = max(1, int(period_node.value))

            if name == "EMA":
                # EMA needs period*3 warmup bars (matches lookback.py _EMA_MULT=3)
                warmup = period * 3
                if size < warmup:
                    return None
                arr = _eval_array(src, ohlcv, size - warmup, size)
            else:
                if size < period:
                    return None
                arr = _eval_array(src, ohlcv, size - period, size)

            # Drop NaN/Inf
            arr = arr[np.isfinite(arr)]
            if len(arr) == 0:
                return None

            if name == "SMA":
                return float(np.mean(arr))
            if name in ("MIN", "LOWEST"):
                return float(np.min(arr))
            if name in ("MAX", "HIGHEST"):
                return float(np.max(arr))
            if name == "EMA":
                return _ema_last(arr, period)

        raise _Unsupported(f"function call {node.name!r}")

    raise _Unsupported(f"unknown node type {type(node).__name__!r}")


def _eval_array(node: Node, ohlcv: np.ndarray, start: int, end: int) -> np.ndarray:
    """Evaluate *node* as a float64 array over ``ohlcv[start:end]``.

    Only supports simple FieldRef arithmetic — no nested window functions or
    bar-shifts (which require additional context rows beyond the window).
    Raises ``_Unsupported`` for anything more complex.
    """
    if isinstance(node, NumberLiteral):
        return np.full(end - start, node.value, dtype=np.float64)

    if isinstance(node, FieldRef):
        idx = _FIELD_IDX.get(node.name.upper())
        if idx is None:
            raise _Unsupported(f"unknown field {node.name!r}")
        return ohlcv[start:end, idx].astype(np.float64)

    if isinstance(node, UnaryOp):
        arr = _eval_array(node.operand, ohlcv, start, end)
        if node.op == "-":
            return -arr
        raise _Unsupported(f"unary op {node.op!r} in array context")

    if isinstance(node, BinOp):
        left = _eval_array(node.left, ohlcv, start, end)
        right = _eval_array(node.right, ohlcv, start, end)
        op = node.op
        if op == "+":
            return left + right
        if op == "-":
            return left - right
        if op == "*":
            return left * right
        if op == "/":
            with np.errstate(divide="ignore", invalid="ignore"):
                return np.where(right != 0, left / right, np.nan)
        raise _Unsupported(f"binary op {op!r} in array context")

    raise _Unsupported(f"array eval of {type(node).__name__!r}")


def _ema_last(data: np.ndarray, span: int) -> float:
    """Return the EMA value at the last element using the ``adjust=False`` convention."""
    alpha = 2.0 / (span + 1)
    ema = float(data[0])
    for v in data[1:]:
        ema = alpha * float(v) + (1.0 - alpha) * ema
    return ema


def _check(node: Node) -> None:
    """Recursively verify that *node* contains no unsupported sub-expressions."""
    if isinstance(node, (NumberLiteral, FieldRef)):
        return
    if isinstance(node, ShiftExpr):
        if not isinstance(node.expr, FieldRef):
            raise _Unsupported("nested shift")
        return
    if isinstance(node, UnaryOp):
        _check(node.operand)
        return
    if isinstance(node, BinOp):
        _check(node.left)
        _check(node.right)
        return
    if isinstance(node, FuncCall):
        name = node.name
        if name in ("SMA", "EMA", "MIN", "LOWEST", "MAX", "HIGHEST") and len(node.args) == 2:
            src, period_node = node.args
            if not isinstance(period_node, NumberLiteral):
                raise _Unsupported("non-literal period")
            # Source must be simple arithmetic — no nested window functions
            _check_array_safe(src)
            return
        raise _Unsupported(f"function {name!r}")
    raise _Unsupported(f"node {type(node).__name__!r}")


def _check_array_safe(node: Node) -> None:
    """Verify that *node* can be passed to ``_eval_array`` (no window functions or shifts)."""
    if isinstance(node, (NumberLiteral, FieldRef)):
        return
    if isinstance(node, UnaryOp):
        _check_array_safe(node.operand)
        return
    if isinstance(node, BinOp):
        _check_array_safe(node.left)
        _check_array_safe(node.right)
        return
    raise _Unsupported(f"not array-safe: {type(node).__name__!r}")
