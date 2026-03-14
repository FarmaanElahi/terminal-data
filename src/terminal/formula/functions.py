"""Function registry for vectorised built-in functions (SMA, EMA, …).

Adding a new function requires:
  1. Write the implementation: ``def my_func(source: np.ndarray, period: int) -> np.ndarray``
  2. Call ``register("MY_FUNC", 2, my_func)``
  3. Done — zero parser changes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from difflib import get_close_matches
from typing import Callable

import numpy as np
import pandas as pd

from terminal.formula.errors import FormulaError

# Type alias for function implementations.
# First arg is always a np.ndarray (the source), remaining are numeric params.
FuncImpl = Callable[..., np.ndarray]

# Lookback function: (source_lb, *period_args) -> int
# source_lb  = lookback of the explicit series argument (1 when all-implicit)
# period_args = the numeric (non-series) arguments, e.g. the rolling window size
LookbackFn = Callable[..., int]


@dataclass(frozen=True, slots=True)
class FuncDef:
    """Metadata about a registered formula function."""

    name: str
    n_args: int  # total args including source
    impl: FuncImpl
    series_args: frozenset[int]
    implicit_series: tuple[str, ...]
    lookback_fn: LookbackFn | None = None


# Global registry — keyed by uppercase function name.
_REGISTRY: dict[str, FuncDef] = {}


def register(
    name: str,
    n_args: int,
    impl: FuncImpl,
    *,
    series_args: set[int] | None = None,
    implicit_series: list[str] | tuple[str, ...] | None = None,
    lookback: LookbackFn | None = None,
) -> None:
    """Register a vectorised function for use in formulas.

    ``lookback`` is an optional callable ``(source_lb, *period_args) -> int``
    that computes the minimum number of rows needed for the last result element
    to be valid.  When provided, ``lookback.py`` uses it automatically — no
    manual case needs to be added there.

    - ``source_lb``  : lookback of the explicit series argument (always 1 for
                       fully-implicit functions such as RSI / RMV).
    - ``period_args``: the numeric (non-series) arguments in declaration order.
    """
    if series_args is None:
        series_args = {0}
    implicit = tuple(s.upper() for s in (implicit_series or ()))
    if not series_args and not implicit:
        raise ValueError(f"{name}: series_args cannot be empty without implicit_series.")
    for idx in series_args:
        if idx < 0 or idx >= n_args:
            raise ValueError(
                f"{name}: series_args index {idx} out of range for {n_args} args."
            )

    _REGISTRY[name.upper()] = FuncDef(
        name=name.upper(),
        n_args=n_args,
        impl=impl,
        series_args=frozenset(series_args),
        implicit_series=implicit,
        lookback_fn=lookback,
    )


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


def _rsi(close: np.ndarray, period: int) -> np.ndarray:
    """Relative Strength Index — Wilder's smoothing (EMA with alpha=1/period)."""
    p = int(period)
    delta = pd.Series(close).diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / p, adjust=False).mean()
    loss = (-delta).clip(lower=0).ewm(alpha=1 / p, adjust=False).mean()
    rs = gain / loss
    return (100 - 100 / (1 + rs)).to_numpy()


def _rmv(
    high: np.ndarray, low: np.ndarray, close: np.ndarray, loopback: int
) -> np.ndarray:
    """Relative Momentum Volatility (RMV)."""
    lb = int(loopback)
    if lb <= 0:
        return np.full_like(np.asarray(close, dtype=np.float64), np.nan, dtype=float)

    high_s = pd.Series(np.asarray(high, dtype=np.float64))
    low_s = pd.Series(np.asarray(low, dtype=np.float64))
    close_s = pd.Series(np.asarray(close, dtype=np.float64))

    # 2-period calculations
    high2 = high_s.rolling(2).max()
    low_of_high2 = high_s.rolling(2).min()
    close2 = close_s.rolling(2).max()
    low_close2 = close_s.rolling(2).min()
    high_of_low2 = low_s.rolling(2).max()
    low2 = low_s.rolling(2).min()

    term1_2p = ((high2 - low_of_high2) / low_close2) * 100
    term2_2p = ((close2 - low_close2) / low_close2) * 100
    term3_2p = ((high_of_low2 - low2) / low2) * 100
    avg_2p = (term1_2p + 1.5 * term2_2p + term3_2p) / 3

    # 3-period calculations
    high3 = high_s.rolling(3).max()
    low_of_high3 = high_s.rolling(3).min()
    close3 = close_s.rolling(3).max()
    low_close3 = close_s.rolling(3).min()

    term1_3p = ((high3 - low_of_high3) / low_close3) * 100
    term2_3p = 1.5 * ((close3 - low_close3) / low_close3) * 100
    avg_3p = (term1_3p + term2_3p) / 2

    combined_avg = (3 * avg_2p + avg_3p) / 4

    highest_combined = combined_avg.rolling(lb).max()
    lowest_combined = combined_avg.rolling(lb).min()

    return (
        ((combined_avg - lowest_combined) / (highest_combined - lowest_combined))
        * 100
    ).to_numpy()


# Register builtins
# lookback lambda signature: (source_lb, *period_args) -> int
register("SMA",     2, _sma,     lookback=lambda src, p: src + p - 1)
register("EMA",     2, _ema,     lookback=lambda src, p: src + p * 3)  # 3× warmup
register("MIN",     2, _min,     lookback=lambda src, p: src + p - 1)
register("MAX",     2, _max,     lookback=lambda src, p: src + p - 1)
register("HIGHEST", 2, _highest, lookback=lambda src, p: src + p - 1)
register("LOWEST",  2, _lowest,  lookback=lambda src, p: src + p - 1)
register("RSI", 1, _rsi, series_args=set(), implicit_series=("C",),
         lookback=lambda _, p: p * 3)          # Wilder's EMA, 3× warmup
register("RMV", 1, _rmv, series_args=set(), implicit_series=("H", "L", "C"),
         lookback=lambda _, lb: lb + 3)        # rolling(2/3) internals + outer window
