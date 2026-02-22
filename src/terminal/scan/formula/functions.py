"""Function registry for vectorised built-in functions (SMA, EMA, …).

Adding a new function requires:
  1. Write the implementation: ``def my_func(source: np.ndarray, period: int) -> np.ndarray``
  2. Call ``register("MY_FUNC", 2, my_func)``
  3. Done — zero parser changes.
"""

from __future__ import annotations

from dataclasses import dataclass
from difflib import get_close_matches
from typing import Callable

import numpy as np
import pandas as pd

from terminal.scan.formula.errors import FormulaError

# Type alias for function implementations.
# First arg is always a np.ndarray (the source), remaining are numeric params.
FuncImpl = Callable[..., np.ndarray]


@dataclass(frozen=True, slots=True)
class FuncDef:
    """Metadata about a registered formula function."""

    name: str
    n_args: int  # total args including source
    impl: FuncImpl


# Global registry — keyed by uppercase function name.
_REGISTRY: dict[str, FuncDef] = {}


def register(name: str, n_args: int, impl: FuncImpl) -> None:
    """Register a vectorised function for use in formulas."""
    _REGISTRY[name.upper()] = FuncDef(name=name.upper(), n_args=n_args, impl=impl)


def get_func(name: str, *, formula: str = "", position: int = 0) -> FuncDef:
    """Look up a function by *name* (case-insensitive).

    Raises ``FormulaError`` with a "Did you mean?" hint when not found.
    """
    key = name.upper()
    func = _REGISTRY.get(key)
    if func is not None:
        return func

    registered = sorted(_REGISTRY)
    close = get_close_matches(key, registered, n=1, cutoff=0.5)
    hint = f"Did you mean {close[0]}?" if close else None
    raise FormulaError(
        f'"{name}" is not a registered function. '
        f"Registered functions: {', '.join(registered) or '(none)'}",
        formula=formula,
        position=position,
        hint=hint,
    )


def registered_names() -> list[str]:
    """Return sorted list of registered function names."""
    return sorted(_REGISTRY)


# ---------------------------------------------------------------------------
# Built-in implementations
# ---------------------------------------------------------------------------


def _sma(source: np.ndarray, period: int) -> np.ndarray:
    """Simple Moving Average — O(n) via pandas rolling."""
    return pd.Series(source).rolling(int(period)).mean().to_numpy()


def _ema(source: np.ndarray, period: int) -> np.ndarray:
    """Exponential Moving Average — seeded with SMA, adjust=False."""
    return pd.Series(source).ewm(span=int(period), adjust=False).mean().to_numpy()


def _min(source: np.ndarray, period: int) -> np.ndarray:
    """Minimum value in a window."""
    return pd.Series(source).rolling(int(period)).min().to_numpy()


def _max(source: np.ndarray, period: int) -> np.ndarray:
    """Maximum value in a window."""
    return pd.Series(source).rolling(int(period)).max().to_numpy()


def _highest(source: np.ndarray, period: int) -> np.ndarray:
    """Highest value in a window."""
    return pd.Series(source).rolling(int(period)).max().to_numpy()


def _lowest(source: np.ndarray, period: int) -> np.ndarray:
    """Lowest value in a window."""
    return pd.Series(source).rolling(int(period)).min().to_numpy()


# Register builtins
register("SMA", 2, _sma)
register("EMA", 2, _ema)
register("MIN", 2, _min)
register("MAX", 2, _max)
register("HIGHEST", 2, _highest)
register("LOWEST", 2, _lowest)
