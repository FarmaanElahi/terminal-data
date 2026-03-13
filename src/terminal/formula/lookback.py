"""Static lookback analysis for formula ASTs.

Given a parsed formula AST, ``compute_lookback()`` returns the minimum number
of DataFrame rows that must be passed to ``evaluate()`` for the last element
(``result[-1]``) to be numerically valid.

This enables selective DataFrame slicing: instead of evaluating a formula over
5 years of data (1825 rows) when only the last row is needed, we pass only the
minimum rows required — e.g. 52 rows for ``SMA(C, 50) + 2-bar shift``.

Lookup rules
------------
- ``NumberLiteral`` → 1  (scalar, shape-compatible with any array)
- ``FieldRef``       → 1  (just the last row)
- ``UnaryOp``        → same as operand
- ``BinOp``          → max(left, right)
- ``ShiftExpr(e,N)`` → lookback(e) + N  (shift eats N rows from the tail)
- ``SMA/MIN/MAX/HIGHEST/LOWEST(src, period)``
                     → lookback(src) + period - 1
- ``EMA(src, period)``
                     → lookback(src) + period × 3
                       (exponential warmup: < 1% initial-condition bias)
- ``RMV(loopback)``  → loopback + 3  (internal rolling(2/3) + outer rolling(lb))
- unknown function   → ``_FALLBACK`` (conservative; still far less than 1825)
"""

from __future__ import annotations

from .ast_nodes import BinOp, FieldRef, FuncCall, Node, NumberLiteral, ShiftExpr, UnaryOp

# Conservative fallback when lookback cannot be determined statically.
# Even this is ~3.6× smaller than 5 years of daily data.
_FALLBACK: int = 500

# EMA/RSI warmup multiplier.
# After period × _EMA_MULT bars, the initial-condition bias is < 1 %.
_EMA_MULT: int = 3


def compute_lookback(node: Node) -> int:
    """Return the minimum number of rows needed for ``result[-1]`` to be valid.

    Always returns at least 1.  Conservative fallbacks ensure results are never
    silently incorrect when the period cannot be determined at parse time.
    """
    return max(1, _lb(node))


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _lb(node: Node) -> int:
    if isinstance(node, NumberLiteral):
        return 1

    if isinstance(node, FieldRef):
        return 1

    if isinstance(node, UnaryOp):
        return _lb(node.operand)

    if isinstance(node, BinOp):
        return max(_lb(node.left), _lb(node.right))

    if isinstance(node, ShiftExpr):
        # Shifting by N moves the window N bars into the past —
        # the inner expression needs its own lookback PLUS N extra rows
        # so that the shifted result[-1] is non-NaN.
        return _lb(node.expr) + node.periods

    if isinstance(node, FuncCall):
        return _func_lb(node)

    return _FALLBACK


def _func_lb(node: FuncCall) -> int:
    name = node.name  # always upper-cased by the parser
    args = node.args

    # ── Rolling window: last value requires `period` valid source rows ───────
    if name in ("SMA", "MIN", "MAX", "HIGHEST", "LOWEST"):
        source_lb = _lb(args[0]) if args else 1
        period = _literal_int(args[1]) if len(args) > 1 else None
        if period is None:
            return _FALLBACK
        return source_lb + period - 1

    # ── EMA: technically needs all history but 3× period gives < 1% error ───
    if name == "EMA":
        source_lb = _lb(args[0]) if args else 1
        period = _literal_int(args[1]) if len(args) > 1 else None
        if period is None:
            return _FALLBACK
        return source_lb + period * _EMA_MULT

    # ── RMV: implicit H/L/C; rolling(2/3) internals + outer rolling(lb) ─────
    if name == "RMV":
        loopback = _literal_int(args[0]) if args else None
        if loopback is None:
            return _FALLBACK
        # rolling(3) needs 3 warm-up rows; then loopback rows of valid combined_avg
        return loopback + 3

    # ── Unknown / user-defined function: best-effort ─────────────────────────
    # Pick the largest numeric argument as a proxy for "period" and apply the
    # EMA multiplier so we don't under-provision.
    if args:
        biggest = max((_literal_int(a) or 0) for a in args)
        if biggest > 0:
            return biggest * _EMA_MULT

    return _FALLBACK


def _literal_int(node: Node) -> int | None:
    """Return the integer value if *node* is a plain ``NumberLiteral``, else ``None``."""
    if isinstance(node, NumberLiteral):
        return max(1, int(node.value))
    return None
