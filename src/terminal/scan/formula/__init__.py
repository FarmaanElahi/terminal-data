"""
Formula Parser Engine — TC2000-style PCF formula language for OHLCV DataFrames.

Public API:
    parse(formula)   → AST (cacheable, re-usable across DataFrames)
    evaluate(ast, df) → np.ndarray (float64 or bool)
    FormulaError     → raised on invalid formulas with position + hint
"""

from terminal.scan.formula.errors import FormulaError
from terminal.scan.formula.evaluator import evaluate
from terminal.scan.formula.fields import register_column, register_derived
from terminal.scan.formula.params import preprocess
from terminal.scan.formula.parser import UserFuncDef, parse

__all__ = [
    "parse",
    "evaluate",
    "preprocess",
    "FormulaError",
    "UserFuncDef",
    "register_column",
    "register_derived",
]
