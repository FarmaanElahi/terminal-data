import pandas as pd
import pandas_ta as ta
import numpy as np


def alpha(d: pd.DataFrame, market_close: pd.Series):
    # 6 Month
    market_return = ta.percent_return(market_close, 6 * 21)
    symbol_return = ta.percent_return(d.close, 6 * 21)
    cols = {
        "alpha_6M": np.nan if market_return is None or symbol_return is None else (symbol_return - market_return) * 100,
    }
    return cols


def relative_strength(d: pd.DataFrame, market_close: pd.Series):
    common_dates = d.index.intersection(market_close.index)
    d = d.loc[common_dates]
    market_close = market_close.loc[common_dates]

    rs_day_periods = [5, 10, 15, 20, 25, 30, 60, 90]

    symbol_return = ta.percent_return(d.close)
    market_return = ta.percent_return(market_close)
    rs_day:pd.Series = symbol_return > market_return

    # Relative Strength
    cols = {}
    for i in rs_day_periods:
        days = rs_day.rolling(i).sum()
        cols[f"RS_{i}D"] = days
        cols[f"RS_{i}D_pct"] = days / i * 100

    # Relative Strength Line
    rs_line: pd.Series = d.close / market_close
    latest_rs_line = 0 if rs_line.empty else rs_line.iloc[-1]
    rs_line_ema_21 = rs_line.ewm(span=21).mean()
    rs_phase = rs_line > rs_line_ema_21

    # Relative Strength New High
    rsnh_period_month = [1, 3, 6, 9, 12]
    for i in rsnh_period_month:
        # Relative Strength New High
        widow = i * 21

        rsnh = latest_rs_line == rs_line.rolling(widow).max()
        cols[f"RSNH_{i}M"] = rsnh

        # Relative Strength New High Before Price
        stock_high = d.close == d.close.rolling(widow).max()
        rsnhbp = rsnh & ~stock_high
        cols[f"RSNHBP_{i}M"] = rsnhbp

    dpm = 21
    dpw = 5
    cols["RS_Phase"] = rs_phase

    # This is used to calculate RS Rating, It is not shame as RS Line
    cols["RS_Value_1D"] = ((d.close / d.close.shift(1)) / (market_close / market_close.shift(1))) - 1
    cols["RS_Value_1W"] = ((d.close / d.close.shift(dpw)) / (market_close / market_close.shift(dpw))) - 1
    cols["RS_Value_1M"] = ((d.close / d.close.shift(dpm)) / (market_close / market_close.shift(dpm))) - 1
    cols["RS_Value_3M"] = ((d.close / d.close.shift(3 * dpm)) / (market_close / market_close.shift(3 * dpm))) - 1
    cols["RS_Value_6M"] = ((d.close / d.close.shift(6 * dpm)) / (market_close / market_close.shift(6 * dpm))) - 1
    cols["RS_Value_9M"] = ((d.close / d.close.shift(9 * dpm)) / (market_close / market_close.shift(9 * dpm))) - 1
    cols["RS_Value_12M"] = ((d.close / d.close.shift(12 * dpm)) / (market_close / market_close.shift(12 * dpm))) - 1

    return cols
