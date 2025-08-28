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


def change(series: pd.Series, periods: int = 1) -> pd.Series:
    """
    Calculate percentage change for stock price momentum analysis.

    Used in technical scanning to identify stocks with specific price momentum
    characteristics. This function is commonly used in scan expressions like
    'change(c) > 0.05' to find stocks with 5% or greater price increases.

    Args:
        series: Stock price series (typically close prices)
        periods: Number of periods to look back for comparison (default: 1)

    Returns:
        pd.Series: Percentage change values in decimal format
                  (0.05 = 5% increase, -0.03 = 3% decrease)

    Examples:
        Single-period change (daily momentum):
        change(close_prices)

        Multi-period change (weekly momentum on daily data):
        change(close_prices, periods=5)

    Common scan expressions:
        - 'change(c) > 0.02' - Stocks up more than 2%
        - 'change(c, 5) > 0.1' - Stocks up more than 10% over 5 periods
        - 'abs(change(c)) > 0.05' - Stocks with significant movement (±5%)
    """
    return series.pct_change(periods=periods, fill_method=None)