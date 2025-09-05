import pandas as pd
import numpy as np


def sma_single(series: pd.Series, window: int) -> pd.Series:
    """Calculate Simple Moving Average for single symbol."""
    return series.rolling(window, min_periods=1).mean()


def ema_single(series: pd.Series, window: int) -> pd.Series:
    """Calculate Exponential Moving Average for single symbol."""
    return series.ewm(span=window, adjust=False).mean()


def prv_single(series: pd.Series, lookback: int = 1) -> pd.Series:
    """Get previous value for single symbol."""
    return series.shift(lookback)


def min_single(series: pd.Series, window: int) -> pd.Series:
    """Calculate rolling minimum for single symbol."""
    return series.rolling(window, min_periods=1).min()


def max_single(series: pd.Series, window: int) -> pd.Series:
    """Calculate rolling maximum for single symbol."""
    return series.rolling(window, min_periods=1).max()


def count_single(series: pd.Series, window: int) -> pd.Series:
    """Calculate rolling count for single symbol."""
    return series.rolling(window, min_periods=1).count()


def count_true_single(series: pd.Series, window: int) -> pd.Series:
    """Calculate rolling sum of True values for single symbol."""
    return series.rolling(window, min_periods=1).sum()


def change(series: pd.Series, periods: int = 1) -> pd.Series:
    """Calculate percentage change for stock price momentum analysis."""
    return series.pct_change(periods=periods).replace([np.inf, -np.inf], np.nan)
