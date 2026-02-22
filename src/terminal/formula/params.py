"""Parameter preprocessor for multi-line formulas.

Extracts ``param NAME = VALUE`` declarations from the top of a formula
and returns the expression body + a params dict.

Usage::

    body, params = preprocess(\"\"\"
        param d = 10
        param threshold = 1.2
        C / SMA(C, d) > threshold
    \"\"\")
    # body = "C / SMA(C, d) > threshold"
    # params = {"D": 10.0, "THRESHOLD": 1.2}
"""

from __future__ import annotations

import re

from terminal.formula.errors import FormulaError
from terminal.formula import fields
from terminal.formula.functions import registered_names

# Reserved names that cannot be used as parameter names
_RESERVED = {"AND", "OR", "NOT", "PARAM"}

_PARAM_RE = re.compile(
    r"^\s*param\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*([0-9]+(?:\.[0-9]+)?)\s*$",
    re.IGNORECASE,
)


def preprocess(formula: str) -> tuple[str, dict[str, float]]:
    """Extract param declarations and return ``(expression_body, params)``.

    Each ``param`` line is removed from the formula. The remaining non-empty
    lines are joined as the expression body.

    Raises ``FormulaError`` on invalid param syntax.
    """
    params: dict[str, float] = {}
    body_lines: list[str] = []

    for lineno, raw_line in enumerate(formula.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue

        # Check if it's a param declaration
        if line.lower().startswith("param ") or line.lower().startswith("param\t"):
            m = _PARAM_RE.match(line)
            if m is None:
                raise FormulaError(
                    f"Invalid param syntax on line {lineno}. "
                    'Expected: param NAME = NUMBER (e.g. "param d = 10")',
                    formula=formula,
                )
            name = m.group(1).upper()
            value = float(m.group(2))

            # Check reserved names
            if name in _RESERVED:
                raise FormulaError(
                    f'"{name}" is a reserved keyword and cannot be used as a parameter name.',
                    formula=formula,
                )

            # Check collision with fields
            if fields.is_known(name):
                raise FormulaError(
                    f'"{name}" is already a field name and cannot be used as a parameter.',
                    formula=formula,
                )

            # Check collision with functions
            if name in registered_names():
                raise FormulaError(
                    f'"{name}" is already a function name and cannot be used as a parameter.',
                    formula=formula,
                )

            # Check duplicate
            if name in params:
                raise FormulaError(
                    f'Parameter "{name}" is defined more than once.',
                    formula=formula,
                )

            params[name] = value
        else:
            body_lines.append(line)

    body = " ".join(body_lines)
    return body, params
