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
from .functions import get_func
from .errors import FormulaError

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
    args = node.args

    # ── Look up the registered function ──────────────────────────────────────
    try:
        func_def = get_func(node.name)
    except FormulaError:
        return _FALLBACK

    # ── Use the function's own lookback_fn when available ────────────────────
    # lookback_fn signature: (source_lb, *period_args) -> int
    # source_lb  = max lookback of all explicit series arguments (1 if all-implicit)
    # period_args = all numeric (non-series) arguments in declaration order
    if func_def.lookback_fn is not None:
        # Compute source_lb from explicit series args
        source_lb = 1
        if func_def.series_args:
            lbs = [_lb(args[i]) for i in func_def.series_args if i < len(args)]
            if lbs:
                source_lb = max(lbs)

        # Collect numeric (period) args — those NOT in series_args
        period_args: list[int] = []
        for i, arg in enumerate(args):
            if i not in func_def.series_args:
                val = _literal_int(arg)
                if val is None:
                    return _FALLBACK  # dynamic period — can't determine statically
                period_args.append(val)

        return func_def.lookback_fn(source_lb, *period_args)

    # ── Fallback for functions registered without a lookback_fn ──────────────
    # Best-effort: use the largest numeric arg × EMA multiplier.
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
