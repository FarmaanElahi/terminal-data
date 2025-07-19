import numpy as np
import pandas as pd
import pandas_ta as ta

from modules.core.provider.base.candles import CandleProvider
from modules.core.provider.upstox.candles import UpstoxCandleProvider
from utils.comparitive import alpha, relative_strength
from utils.pandas_utils import get_latest
from utils.price_volume_action import volume_action, price_action

market_ticker = {"NSE": "NSE:NIFTY", "BSE": "BSE:SENSEX"}


async def get_market_candles(candle_provider: CandleProvider):
    market_candles = {}
    async for ticker, df, error in candle_provider.stream(list(market_ticker.values())):
        if not error:
            market_candles[ticker] = df
    return market_candles


async def get_technicals(df: pd.DataFrame, tickers: list[str]):
    candle_provider = UpstoxCandleProvider()
    await  candle_provider.prepare()

    technical_data = []
    market_candles = await get_market_candles(candle_provider)

    missing_tickers = []
    async for ticker, d, error in candle_provider.stream(tickers):
        if not error and not d.empty:
            row = df.loc[ticker]
            market_d = market_candles[market_ticker[row.exchange]]
            technical = get_technical(ticker, row, d, market_d)
            technical_data.append(technical)
        else:
            missing_tickers.append(ticker)

    technical = pd.DataFrame(technical_data)
    technical = technical.set_index(["ticker"])
    return missing_tickers, technical


def get_technical(ticker: str, row: pd.Series, d: pd.DataFrame, market_d: pd.DataFrame):
    # Read the ticker data
    cols = {"ticker": ticker}
    shares_float = row.shares_float
    last_earning_date = row.earnings_release_date

    # Fix the missing volume
    if d.volume.empty:
        d['volume'] = np.nan

    w = to_weekly_candles(d)
    m = to_monthly_candles(d)
    y = to_yearly_candles(d)

    if d.volume.empty:
        d['volume'] = np.nan

    last_trading_day = d.index[-1]
    year_back = last_trading_day - pd.DateOffset(years=1)
    d_w52 = d[d.index > year_back]

    d_since_earning = d[d.index >= last_earning_date]

    # Meta
    days_since_earning = len(d_since_earning)
    cols = cols | {"days_since_latest_earning": pd.Series([days_since_earning])}

    # OHLCV
    cols = cols | ohlcv(d, name='day') | ohlcv(d, name='prev_day', shift=1)
    cols = cols | ohlcv(w, name='week') | ohlcv(w, name='prev_week', shift=1)
    cols = cols | ohlcv(m, name='month') | ohlcv(m, name='prev_month', shift=1)
    cols = cols | ohlcv(y, name='year') | ohlcv(y, name='prev_year', shift=1)

    # Price Volume Action
    cols = cols | price_action(d, d_w52, w, m, y, days_since_earning, last_trading_day)
    cols = cols | volume_action(d, d_w52, d_since_earning, w, shares_float, last_trading_day)

    sma_200_close = d.close.rolling(200).mean()
    # Indicator
    cols = cols | indicators(d, w)
    # SMA Comparison Months Back
    cols = cols | sma_comparison(d, sma_200_close)
    cols = cols | sma_vs_ema_slope(d, "D", [10, 20, 30, 40, 50, 100, 200])
    # ADR
    cols = cols | adr(d)
    # ADR
    cols = cols | atr(d)

    # RMV
    cols = cols | rmv(d)

    # Momentum
    cols = cols | momentum(d)

    #
    # Comparative
    market_d = market_d[~market_d.index.duplicated(keep='first')]
    market_close = market_d.reindex(d.index).close.fillna(0)

    cols = cols | alpha(d, market_close)

    cols = cols | relative_strength(d, market_close)

    cols = cols | stockbee(d)

    return {k: get_latest(v) for k, v in cols.items()}


def to_weekly_candles(d: pd.DataFrame):
    # TODO: Try with .resample('W-MON', label='left', closed='left')

    d = d.copy()
    # Step 1: Adjust the timestamp index to the start of the week (Monday 12:00 AM UTC)
    d["Week_Start"] = d.index.to_period("W").start_time

    # Step 2: Group by the week start
    w: pd.DataFrame = (d.groupby("Week_Start").agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    }).reset_index())

    w = w.rename(columns={'Week_Start': 'timestamp'}).set_index('timestamp')
    return w


def to_monthly_candles(d: pd.DataFrame):
    d = d.copy()
    # Step 1: Adjust the timestamp index to the start of the week (Monday 12:00 AM UTC)
    d["Month_Start"] = d.index.to_period("M").start_time

    # Step 2: Group by the week start
    m = (d.groupby("Month_Start").agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    }).reset_index())

    m = m.rename(columns={'Month_Start': 'timestamp'}).set_index('timestamp')
    return m


def to_yearly_candles(m: pd.DataFrame):
    return m.resample('YS').agg({
        'open': 'first',  # First Open in the year
        'high': 'max',  # Maximum High in the year
        'low': 'min',  # Minimum Low in the year
        'close': 'last',  # Last Close in the year
        'volume': 'sum'  # Sum of Volume in the year
    })


def ohlcv(candle: pd.DataFrame, name: str, shift: int = 0) -> dict[str, pd.Series]:
    return {
        f"{name}_open": candle.open if shift == 0 else candle.open.shift(shift),
        f"{name}_high": candle.high if shift == 0 else candle.high.shift(shift),
        f"{name}_low": candle.low if shift == 0 else candle.low.shift(shift),
        f"{name}_close": candle.close if shift == 0 else candle.close.shift(shift),
        f"{name}_volume": candle.volume if shift == 0 else candle.volume.shift(shift),
    }


def indicators(d: pd.DataFrame, w: pd.DataFrame):
    # Link: https://deepvue.com/knowledge-base/technical/
    prev = d.shift(1)
    prev_2 = d.shift(2)
    prev_w = w.shift(1)
    ema_4_high = d.high.ewm(span=4).mean()
    ema_10_close = d.close.ewm(span=10).mean()
    ema_21_close = d.close.ewm(span=21).mean()
    sma_50_close = d.close.rolling(50).mean()
    w_ema_5_close = w.close.ewm(span=5).mean()
    w_sma_10_close = w.close.rolling(10).mean()

    inside = safe_call_cdl_pattern(d, name='inside')
    inside_week = safe_call_cdl_pattern(w, name='inside')
    cols = {
        "inside_day": inside,
        "double_inside_day": inside & safe_call_cdl_pattern(prev, name='inside'),
        "inside_week": inside_week,
        "double_inside_week": inside_week & safe_call_cdl_pattern(prev_w, name='inside'),
        "outside_day": safe_call_cdl_pattern(d, name='engulfing'),
        "outside_week": safe_call_cdl_pattern(w, name='engulfing'),
        "outside_bullish_day": (d.open < prev.low) & (d.close > prev.high),
        "outside_bearish_day": (d.open > prev.high) & (d.close < prev.low),
        "outside_bullish_week": (w.open < prev_w.low) & (w.close > prev_w.high),
        "outside_bearish_week": (w.open > prev_w.high) & (w.close < prev_w.low),
        "wick_play": ((d.low > prev.open) | (d.low > prev.close)) & (d.high < prev.high),
        "in_the_wick": (d.open < prev.high) & ((d.low > prev.low) | (d.open > prev.high)),
        "3_line_strike_bullish": safe_call_cdl_pattern(d, name='3linestrike'),
        "3_line_strike_bearish": safe_call_cdl_pattern(d, name='3linestrike', bearish=True),
        "3_bar_break": d.close > prev.high.rolling(3).max(),
        "bullish_reversal": (d.low < prev.low) & d.close > prev.close,
        "upside_reversal": (d.low < prev.low) & (d.close > (d.high + d.low) / 2),
        "oops_reversal": (d.open < prev.low) & (d.close > prev.low),
        "key_reversal": (d.open < prev.low) & (d.close < prev.high),
        "pocket_pivot": pocket_pivot(d, prev),
        "volume_dry_up": d.volume == d.volume.rolling(window=10, min_periods=1).min(),
        "slingshot": (d.close > ema_4_high) & (d.close <= ema_4_high.shift(1)),
        "minicoil": minicoil(d, prev, prev_2),
        "3_week_tight": three_week_tight(w),
        "5_week_up": five_week_up(w),
        "high_tight_flag": high_tight_flag(d),
        "ants": ants(d, prev),
        "power_trend": power_trend(d, ema_21_close, sma_50_close),
        "power_of_three": power_of_three(d, ema_10_close, ema_21_close, sma_50_close),
        "launchpad": launchpad_daily(ema_21_close, sma_50_close),
        "launchpad_weekly": launchpad_weekly(w_ema_5_close, w_sma_10_close),
        # TODO: Green Line Breakout
        "doji": safe_call_cdl_pattern(d, name='doji'),
        "morning_star": safe_call_cdl_pattern(d, name='morningstar'),
        "evening_star": safe_call_cdl_pattern(d, name='eveningstar'),
        "shooting_star": safe_call_cdl_pattern(d, name='shootingstar'),
        "hammer": safe_call_cdl_pattern(d, name='hammer'),
        "inverted_hammer": safe_call_cdl_pattern(d, name='invertedhammer'),
        "bullish_harami": safe_call_cdl_pattern(d, name='harami'),
        "bearish_harami": safe_call_cdl_pattern(d, name='harami', bearish=False),
        # TODO: Bullish engulfing and bearish engulfing
        # TODO: Bullish kicker and bearish engulfing,
        "piercing_line": safe_call_cdl_pattern(d, name='piercing'),
        "hanging_man": safe_call_cdl_pattern(d, name='hangingman'),
        "dark_cloud_cover": safe_call_cdl_pattern(d, name='darkcloudcover'),
        "gravestone_doji": safe_call_cdl_pattern(d, name='gravestonedoji'),
        "3_back_crows": safe_call_cdl_pattern(d, name='3blackcrows'),
        "dragonfly_doji": safe_call_cdl_pattern(d, name='dragonflydoji'),
        "3_white_soldiers": safe_call_cdl_pattern(d, name='3whitesoldiers'),
        "sigma_spike": sigma_spike(d),
        "stan_weinstein_stage": stan_weinstein_stage_analysis(d),
    }
    return cols


def sigma_spike(d: pd.DataFrame):
    # Calculate daily percent change
    day_chang_pct = ta.percent_return(d.close) * 100
    # Calculate standard deviation of daily percent changes over the past 20 days
    volatility_20_days = day_chang_pct.rolling(window=20).std()
    # Calculate Sigma Spike
    return day_chang_pct / volatility_20_days


def launchpad_daily(ema_21: pd.Series, sma_50: pd.Series):
    # Short and long-term MAs close to each other (< 2%)
    return (ema_21 / sma_50 - 1).abs() < 0.02


def launchpad_weekly(ema_5: pd.Series, sma_10: pd.Series):
    # Short and long-term MAs close to each other (< 2%)
    return (ema_5 / sma_10 - 1).abs() < 0.02


def power_of_three(d: pd.DataFrame, ema_10: pd.Series, ema_21: pd.Series, sma_50: pd.Series):
    return (
            ta.cross(d.close, ema_10)  # Close above 10
            &
            ta.cross(d.close, ema_21)  # Close above 21
            &
            ta.cross(d.close, sma_50)  # Close above 50 SMA
    )


def power_trend(d: pd.DataFrame, ema_21: pd.Series, sma_50: pd.Series):
    return (
            (d.close > ema_21)  # Close above 21
            &
            (ema_21 > sma_50)  # 21 EMA > 50 SMA
            &
            (d.close > sma_50)  # Close above 50 SMA
    )


def ants(d: pd.DataFrame, prev: pd.DataFrame):
    return (
            ((d.close > prev.close).rolling(window=15).sum() >= 12)  # 12/15 days up
            &
            (d.volume > d.volume.rolling(window=15).mean())  # Increase in average volume
    )


def high_tight_flag(d: pd.DataFrame):
    rolling8 = d.close.rolling(window=8)
    rolling3_high = d.high.rolling(window=3)
    rolling3_low = d.low.rolling(window=3)
    rolling_3_close = d.close.rolling(window=3)
    # 90% sharp move
    sharp_move = rolling8.max() / rolling8.min() >= 1.90
    # Tight (<= 25%) consolidation
    consolidation = (rolling3_high.max() - rolling3_low.min()) / rolling_3_close.mean() <= 0.025
    return sharp_move & consolidation


def five_week_up(w: pd.DataFrame):
    w_close = w.close
    w_close1 = w_close.shift(1)
    w_close2 = w_close.shift(2)
    w_close3 = w_close.shift(3)
    w_close4 = w.close.shift(4)
    w_close5 = w.close.shift(5)

    return ((w_close > w_close1) &
            (w_close1 > w_close2) &
            (w_close2 > w_close3) &
            (w_close3 > w_close4) &
            (w_close4 > w_close5))


def three_week_tight(w: pd.DataFrame):
    rolling_3 = w.close.rolling(window=3)
    # Range is within 1.5%
    return ((rolling_3.max() - rolling_3.min()) / rolling_3.mean()) <= 0.015


def minicoil(d: pd.DataFrame, prev: pd.DataFrame, prev_2: pd.DataFrame):
    return (
            (prev.close < prev_2.close) & (prev.low > prev_2.low)  # day2_inside
            &
            (d.high < prev_2.high) & (d.low > prev_2.low)  # day1_inside
    )


def pocket_pivot(d: pd.DataFrame, prev: pd.DataFrame):
    price_check = d.close > prev.close
    negative_volume = d.volume.where(d.close < prev.close, 0)
    max_negative_vol_in10_days = negative_volume.rolling(window=10, min_periods=1).max()
    volume_check = d.volume > max_negative_vol_in10_days
    return price_check & volume_check


def stan_weinstein_stage_analysis(d: pd.DataFrame):
    # TODO
    # Stan
    # Weinstein
    # Stages(1
    # A, 1, 2
    # A, 2, 3
    # A, 3, 4, 4
    # B -)  #
    return "-"


def sma_comparison(d: pd.DataFrame, sma_200: pd.Series):
    return {
        f"sma_200_vs_sma_200_{i}M_ago": sma_200 > ta.sma(d.close.shift(21 * i)) for i in range(7)
    }


def sma_vs_ema_slope(d: pd.DataFrame, freq: str, period: list[int]):
    cols = {}
    for i in period:
        ma = d.close.rolling(i).mean()
        ma_shifted = ma.shift(1)
        ma_slope = (ma - ma_shifted) / ma_shifted * 100
        adr_10 = (d.high - d.low).rolling(10).mean() / d.close * 100
        ma_vs_adr_10 = ma_slope / adr_10

        cols[f"sma_{i}{freq}"] = ma
        cols[f"{i}{freq}sma_vs_ema_slope_pct"] = ma_slope
        cols[f"{i}{freq}sma_vs_ema_slope_adr"] = ma_vs_adr_10
    return cols


def adr(d: pd.DataFrame):
    period = [1, 2, 5, 10, 14, 20]
    cols = {}
    for i in period:
        rng = d.high - d.low
        adr_value = rng.rolling(i).mean()
        adr_pct = adr_value / d.close * 100
        cols[f"ADR_{i}D"] = adr_value
        cols[f"ADR_pct_{i}D"] = adr_pct
    return cols


def atr(d: pd.DataFrame):
    period = [2, 5, 10, 14, 20]
    cols = {}
    for i in period:
        cols[f"ATR_{i}D"] = ta.atr(d.high, d.low, d.close, i)

    return cols


def safe_call_cdl_pattern(d: pd.DataFrame, name: str, bearish=False) -> pd.Series | bool:
    # noinspection PyBroadException
    try:
        result = ta.cdl(d.open, d.high, d.low, d.close, name=name)
        if len(result.columns) == 0:
            result = None
    except:
        result = None

    if result is None:
        return False

    series = result[result.columns[0]]
    if bearish:
        return series < 0
    return series > 0


def compute_rmv(df: pd.DataFrame, loopback: int) -> pd.Series:
    """
    Compute RMV indicator from a DataFrame with columns: 'high', 'low', 'close'.
    Returns a Pandas Series containing the RMV values.
    """

    high = df.high
    low = df.low
    close = df.close

    # 2-period calculations
    high2 = high.rolling(2).max()
    low_of_high2 = high.rolling(2).min()
    close2 = close.rolling(2).max()
    low_close2 = close.rolling(2).min()
    high_of_low2 = low.rolling(2).max()
    low2 = low.rolling(2).min()

    term1_2p = ((high2 - low_of_high2) / low_close2) * 100
    term2_2p = ((close2 - low_close2) / low_close2) * 100
    term3_2p = ((high_of_low2 - low2) / low2) * 100
    avg_2p = (term1_2p + 1.5 * term2_2p + term3_2p) / 3

    # 3-period calculations
    high3 = high.rolling(3).max()
    low_of_high3 = high.rolling(3).min()
    close3 = close.rolling(3).max()
    low_close3 = close.rolling(3).min()

    term1_3p = ((high3 - low_of_high3) / low_close3) * 100
    term2_3p = 1.5 * ((close3 - low_close3) / low_close3) * 100
    avg_3p = (term1_3p + term2_3p) / 2

    combined_avg = (3 * avg_2p + avg_3p) / 4

    # Normalize RMV over loopback
    highest_combined = combined_avg.rolling(loopback).max()
    lowest_combined = combined_avg.rolling(loopback).min()

    return ((combined_avg - lowest_combined) / (highest_combined - lowest_combined)) * 100


def rmv(d: pd.DataFrame):
    """
    Compute relative ATR (0–100 scale) using pandas-ta.

    Parameters:
        d (pd.DataFrame): Must contain 'high', 'low', 'close'
    """

    period = [5, 10, 15, 20]
    cols = {}

    for loopback in period:

        if len(d) < loopback:
            cols[f'RMV_{loopback}D'] = None
            continue

        cols[f'RMV_{loopback}D'] = compute_rmv(d, loopback)

    return cols


def momentum(d: pd.DataFrame, short_period=20, long_period=50, accel_periods=(5, 10, 15, 20, 21)):
    """
    Calculate momentum and momentum acceleration for multiple periods.

    Args:
        d (pd.DataFrame): DataFrame with price data
        short_period (int): Short period for momentum calculation
        long_period (int): Long period for momentum calculation
        accel_periods (list): List of periods to calculate acceleration for

    Returns:
        dict: Dictionary containing momentum and acceleration values for each period
    """
    # Get the actual length of close data
    close_length = len(d.close)

    # Calculate base momentum as before
    effective_short_period = min(short_period, close_length)
    effective_long_period = min(long_period, close_length)

    mom_short = (d.close - d.close.shift(effective_short_period)) * 100 / d.close.shift(effective_short_period) / effective_short_period
    mom_long = (d.close - d.close.shift(effective_long_period)) * 100 / d.close.shift(effective_long_period) / effective_long_period
    moma = mom_short + mom_long

    # Dictionary to store results
    results = {
        'momentum': moma
    }

    # Calculate acceleration for different periods
    for period in accel_periods:
        effective_accel_period = min(period, close_length)
        # Calculate momentum acceleration for this period
        momentum_acceleration = (moma - moma.shift(effective_accel_period)) / effective_accel_period
        results[f'momentum_acc_{period}D'] = momentum_acceleration

    return results


def stockbee(d: pd.DataFrame):
    return {
        # M20
        "c_by_min_c_7": d.close / d.close.rolling(7).min(),
        "c/minc7": d.close / d.close.rolling(7).min(),
        "c_by_min_c_10": d.close / d.close.rolling(10).min(),
        "c/minc10": d.close / d.close.rolling(10).min(),
        "c_by_min_c_14": d.close / d.close.rolling(14).min(),
        "c/minc14": d.close / d.close.rolling(14).min(),
        "c_by_min_c_21": d.close / d.close.rolling(21).min(),
        "c/minc21": d.close / d.close.rolling(21).min(),
        "c_by_min_c_30": d.close / d.close.rolling(30).min(),
        "c/minc30": d.close / d.close.rolling(30).min(),

        #TI65
        "avgc7_by_avgc65": d.close.rolling(7).mean() / d.close.rolling(65).mean(),
        "avgc7/avgc65": d.close.rolling(7).mean() / d.close.rolling(65).mean(),

        #MDT
        "c/avgc126": d.close / d.close.rolling(126).mean(),
        #MDT25
        "c/avgc126.25": (d.close / d.close.rolling(126).mean()).shift(25),
        "c/avgc126.50": (d.close / d.close.rolling(126).mean()).shift(25),
    }
