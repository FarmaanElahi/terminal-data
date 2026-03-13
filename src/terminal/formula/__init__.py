"""
Formula Parser Engine — TC2000-style PCF formula language for OHLCV DataFrames.

Public API:
    parse(formula)   → AST (cacheable, re-usable across DataFrames)
    evaluate(ast, df) → np.ndarray (float64 or bool)
    FormulaError     → raised on invalid formulas with position + hint
"""

from terminal.formula.errors import FormulaError
from terminal.formula.evaluator import evaluate
from terminal.formula.fields import register_column, register_derived
from terminal.formula.lookback import compute_lookback
from terminal.formula.params import preprocess
from terminal.formula.parser import UserFuncDef, parse
from terminal.formula.scalar import can_scalar_eval, scalar_last

__all__ = [
    "parse",
    "evaluate",
    "preprocess",
    "compute_lookback",
    "can_scalar_eval",
    "scalar_last",
    "FormulaError",
    "UserFuncDef",
    "register_column",
    "register_derived",
]
