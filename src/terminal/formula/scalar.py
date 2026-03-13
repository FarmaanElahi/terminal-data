"""Zero-allocation scalar evaluation for simple arithmetic formula ASTs.

For formulas that contain only arithmetic/comparisons on OHLCV field references
(``C``, ``O``, ``H``, ``L``, ``V``) and bar-shifts (``C.1``, ``H.5``), the
result at the last bar can be computed directly from the raw numpy arrays
stored in ``OHLCStore`` — with **no pandas DataFrame allocation at all**.

This is used as the inner fast-path in the screener column evaluator.
Formulas that reference window functions (``SMA``, ``EMA``, ``RMV``, …) or
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
        # No function calls in scalar mode — they need the full numpy array.
        raise _Unsupported(f"function call {node.name!r}")

    raise _Unsupported(f"unknown node type {type(node).__name__!r}")


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
    # FuncCall or unknown → not scalar-safe
    raise _Unsupported(f"node {type(node).__name__!r}")
