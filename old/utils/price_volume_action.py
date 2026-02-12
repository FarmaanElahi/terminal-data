import numpy as np
import pandas as pd


def get_price_volume_action():
    pass


def price_action(
        d: pd.DataFrame,
        d_w52: pd.DataFrame,
        w: pd.DataFrame,
        m: pd.DataFrame,
        y: pd.DataFrame,
        days_since_earning: int,
        last_trading_day: pd.Timestamp
):
    high_52_week = d_w52.high.max()
    low_52_week = d_w52.low.min()
    all_time_high = d.high.max()
    all_time_low = d.low.min()
    earning_open = d.open.shift(days_since_earning)

    cols = price_compare(d)

    # VWAP
    cols = cols | vwap(d, 'daily') | vwap(w, 'weekly') | vwap(m, 'monthly') | vwap(y, 'yearly')

    # Price Change
    cols = cols | price_change_close(d, [1, 2, 3, 4], 'D') | price_change_close(w, range(1, 4), 'W')
    cols = cols | price_change_close(m, range(1, 12), 'M') | price_change_close(y, range(1, 5), 'Y')

    # Price Performance
    cols = cols | price_performance(d)

    # SMA
    cols = cols | sma(d.close, [5, 10, 20, 30, 40, 50, 100, 200], 'price', 'D', compare=True)
    cols = cols | sma(w.close, [10, 20, 30, 40, 50], 'price', 'W', compare=True)

    # EMA
    cols = cols | ema(d.close, [5, 10, 21, 30, 40, 50, 65], 'price', 'D', compare=True)

    # High Low
    cols = cols | {
        "price_change_today_pct": cols['price_change_pct_1D'],
        "price_change_prev_week_close_pct": cols['price_change_pct_1W'],
        "high_52_week": high_52_week,
        "low_52_week": low_52_week,
        "high_52_week_today": d_w52.high.idxmax() == last_trading_day,
        "low_52_week_today": d_w52.low.idxmax() == last_trading_day,
        "away_from_52_week_high_pct": (d_w52.close - high_52_week) / high_52_week * 100,
        "away_from_52_week_low_pct": (d_w52.close - low_52_week) / low_52_week * 100,
        "all_time_high": all_time_high,
        "all_time_low": all_time_low,
        "all_time_high_today": d.high.idxmax() == last_trading_day,
        "all_time_low_today": d.low.idxmax() == last_trading_day,
        "away_from_all_time_high_pct": (d.close - all_time_high) / all_time_high * 100,
        "away_from_all_time_low_pct": (d.close - all_time_low) / all_time_low * 100,
    }

    # Recent Price Change Comparison abs
    cols = cols | {
        "price_change_today_abs": d.close - d.close.shift(1),
        "price_change_from_open_abs": d.close - d.open,
        "price_change_from_high_abs": d.close - d.high,
        "price_change_from_low_abs": d.close - d.low,
    }

    # Recent Price Change Comparison PCT
    cols = cols | {
        "price_change_from_open_pct": cols['price_change_from_open_abs'] / d.open * 100,
        "price_change_from_high_pct": cols['price_change_from_high_abs'] / d.high * 100,
        "price_change_from_low_pct": cols['price_change_from_low_abs'] / d.low * 100,
        "price_change_curr_week_open_pct": (w.close - w.open) / w.open * 100,
        "price_change_since_earning_pct": (d.close - earning_open) / earning_open * 100,
    }

    # Closing Range
    cols = cols | {
        "dcr": ((d.close - d.low) / (d.high - d.low)) * 100,
        "wcr": ((w.close - w.low) / (w.high - w.low)) * 100,
        "mcr": ((m.close - m.low) / (m.high - m.low)) * 100,
    }

    # Gaps
    cols = cols | gap(d, "D") | gap(w, "W") | gap(m, "M")

    # Up/Down
    cols = cols | up_down(d, "D", [20, 50])

    return cols


def volume_action(
        d: pd.DataFrame,
        d_w52: pd.DataFrame,
        d_since_earning: pd.DataFrame,
        w: pd.DataFrame,
        shares_float,
        last_trading_day
):
    cols = {
        "highest_vol_since_earning": False if len(
            d_since_earning.volume) == 0 else d_since_earning.volume.idxmax() == last_trading_day,
        "highest_vol_in_1_year": False if len(d_w52.volume) == 0 else d_w52.volume.idxmax() == last_trading_day,
        "highest_vol_ever": False if len(d.volume) == 0 else d.volume.idxmax() == last_trading_day,
        "vol_vs_yesterday_vol": d.volume.pct_change(periods=1, fill_method=None) * 100,
        "week_vol_vs_prev_week_vol": w.volume.pct_change(periods=1, fill_method=None) * 100,
    }

    # SMA
    daily_periods = [5, 10, 20, 21, 30, 40, 50, 63, 100, 126, 189, 200, 252]
    weekly_periods = [10, 20, 30, 40, 50]
    cols = cols | sma(d.volume, daily_periods, 'vol', 'D', compare=True, relative=True, run_rate=True)
    cols = cols | sma(w.volume, weekly_periods, 'vol', 'W', compare=True, relative=True, run_rate=True)

    # Price Volume
    price_volume = d.close * d.volume
    cols = cols | {"price_volume": price_volume}
    cols = cols | sma(price_volume, daily_periods, 'price_volume', 'D')

    # Float Turnover
    total_float = shares_float
    float_turnover = d.volume / total_float * 100
    cols = cols | {"float_turnover": float_turnover}
    cols = cols | sma(float_turnover, daily_periods, 'float_turnover', 'D', compare=True)

    return cols


def price_compare(d: pd.DataFrame):
    prev = d.shift(1)
    prev_high = prev.high
    prev_low = prev.low
    prev_close = prev.close
    prev_open = prev.open
    return {
        "day_high_gt_prev_high": d.high > prev_high,
        "day_low_gt_prev_low": d.low > prev_low,
        "day_open_gt_prev_open": d.open > prev_open,
        "day_close_gt_prev_close": d.close > prev_close,
        "day_high_lt_prev_high": d.high < prev_high,
        "day_low_lt_prev_low": d.low < prev_low,
        "day_open_lt_prev_open": d.open < prev_open,
        "day_close_lt_prev_close": d.close < prev_close,
        "day_open_eq_high": d.open == d.high,
        "day_open_eq_low": d.open == d.low,
    }


def price_performance(d: pd.DataFrame):
    return {
        "price_perf_1D": d.close.pct_change(1) * 100,
        "price_perf_1W": d.close.pct_change(5) * 100,
        "price_perf_2W": d.close.pct_change(2 * 5) * 100,
        "price_perf_1M": d.close.pct_change(21) * 100,
        "price_perf_3M": d.close.pct_change(3 * 21) * 100,
        "price_perf_6M": d.close.pct_change(6 * 21) * 100,
        "price_perf_9M": d.close.pct_change(9 * 21) * 100,
        "price_perf_12M": d.close.pct_change(12 * 21) * 100,
    }


def price_change_close(candle: pd.DataFrame, periods: list[int] | range, name: str) -> dict[str, pd.Series]:
    return {
        f"price_change_pct_{i}{name}": (candle.close.pct_change(periods=i, fill_method=None) * 100) for i in periods
    }


def vwap(candle: pd.DataFrame, name: str) -> dict[str, pd.Series]:
    v = (candle.high + candle.low + candle.close) / 3
    away = (candle.close - v) / v * 100
    return {
        f'{name}_vwap': v,
        f'away_from_{name}_vwap_pct': away,
        f'price_above_{name}_vwap': candle.close > v,
    }


def sma(series: pd.Series, periods: list[int] | range, name: str, freq: str, compare=False, relative=False,
        run_rate=False) -> dict[
    str, pd.Series]:
    def to_key(i: int):
        return f"{name}_sma_{i}{freq}"

    def to_compare_key(i: int):
        return f"{name}_vs_{name}_sma_{i}{freq}"

    def to_relative_key(i: int):
        return f"relative_{name}_{i}{freq}"

    def to_run_rate(i: int):
        return f"run_rate_{name}_{i}{freq}"

    cols = {
        to_key(i): series.rolling(i).mean() for i in periods
    }

    if compare:
        cols = cols | {
            to_compare_key(i): (series - cols[to_key(i)]) / cols[to_key(i)] * 100 for i in periods
        }

    if relative:
        cols = cols | {
            to_relative_key(i): series / cols[to_key(i)] for i in periods
        }

    if run_rate:
        cols = cols | {
            to_run_rate(i): series / cols[to_key(i)] * 100 for i in periods
        }

    return cols


def ema(series: pd.Series, periods: list[int] | range, name: str, freq: str, compare=False, relative=False,
        run_rate=False) -> dict[
    str, pd.Series]:
    def to_key(i: int):
        return f"{name}_ema_{i}{freq}"

    def to_compare_key(i: int):
        return f"{name}_vs_{name}_ema_{i}{freq}"

    def to_relative_key(i: int):
        return f"relative_{name}_{i}{freq}"

    def to_run_rate(i: int):
        return f"run_rate_{name}_{i}{freq}"

    cols = {
        to_key(i): series.rolling(i).mean() for i in periods
    }

    if compare:
        cols = cols | {
            to_compare_key(i): (series - cols[to_key(i)]) / cols[to_key(i)] * 100 for i in periods
        }

    if relative:
        cols = cols | {
            to_relative_key(i): series / cols[to_key(i)] for i in periods
        }

    if run_rate:
        cols = cols | {
            to_run_rate(i): series / cols[to_key(i)] * 100 for i in periods
        }

    return cols


def gap(candle: pd.DataFrame, freq: str):
    prev_close = candle.close.shift(1)
    gap_dollar = candle.open - prev_close
    gap_pct = gap_dollar / prev_close * 100
    unfilled_gap_dollar = ((candle.low.where(candle.low > prev_close, other=np.nan) - prev_close)
                           .where(candle.high < prev_close, candle.high - prev_close))

    unfilled_gap_pct = unfilled_gap_dollar / prev_close * 100
    return {
        f"gap_dollar_{freq}": gap_dollar,
        f"unfilled_gap_{freq}": unfilled_gap_dollar,
        f"gap_pct_{freq}": gap_pct,
        f"unfilled_gap_pct_{freq}": unfilled_gap_pct
    }


def up_down(candle: pd.DataFrame, freq: str, period: list[int]) -> dict[str, pd.Series]:
    cols: dict[str, pd.Series] = {}
    for i in period:
        c = candle.tail(i)
        change = c.close - c.open
        up = c[change > 0].volume.sum()
        down = c[change < 0].volume.sum()
        cols[f"up_down_day_{i}{freq}"] = up / down if down != 0 else np.nan
    return cols
