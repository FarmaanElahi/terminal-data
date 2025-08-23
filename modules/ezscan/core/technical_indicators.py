"""
Technical indicator functions optimized for single-symbol operations.

These functions are designed to work with individual symbol DataFrames
for maximum performance without groupby overhead.
"""

import pandas as pd


def sma_single(series: pd.Series, window: int) -> pd.Series:
    """
    Simple Moving Average for single symbol.

    Args:
        series: Price series
        window: Number of periods

    Returns:
        pd.Series: SMA values
    """
    return series.rolling(window, min_periods=1).mean()


def ema_single(series: pd.Series, window: int) -> pd.Series:
    """
    Exponential Moving Average for single symbol.

    Args:
        series: Price series
        window: Number of periods

    Returns:
        pd.Series: EMA values
    """
    return series.ewm(span=window, adjust=False).mean()


def prv_single(series: pd.Series, lookback: int = 1) -> pd.Series:
    """
    Previous value for single symbol.

    Args:
        series: Input series
        lookback: Number of periods to look back

    Returns:
        pd.Series: Shifted series
    """
    return series.shift(lookback)


def min_single(series: pd.Series, window: int) -> pd.Series:
    """
    Rolling minimum for single symbol.

    Args:
        series: Input series
        window: Rolling window size

    Returns:
        pd.Series: Rolling minimum values
    """
    return series.rolling(window, min_periods=1).min()


def max_single(series: pd.Series, window: int) -> pd.Series:
    """
    Rolling maximum for single symbol.

    Args:
        series: Input series
        window: Rolling window size

    Returns:
        pd.Series: Rolling maximum values
    """
    return series.rolling(window, min_periods=1).max()


def count_single(series: pd.Series, window: int) -> pd.Series:
    """
    Rolling count for single symbol.

    Args:
        series: Input series
        window: Rolling window size

    Returns:
        pd.Series: Rolling count values
    """
    return series.rolling(window).count()


def count_true_single(series: pd.Series, window: int) -> pd.Series:
    """
    Rolling sum (count of True values) for single symbol.

    Args:
        series: Boolean series
        window: Rolling window size

    Returns:
        pd.Series: Rolling sum values
    """
    return series.rolling(window, min_periods=1).sum()
