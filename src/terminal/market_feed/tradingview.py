import logging
import time
from typing import AsyncGenerator

import pandas as pd

from .provider import PartitionedProvider, _extract_exchange
from terminal.tradingview.scanner import TradingViewScanner

logger = logging.getLogger(__name__)


class TradingViewDataProvider(PartitionedProvider):
    """DataProvider that fetches daily OHLCV data from TradingView.

    Supports both a Scanner REST API snapshot and full historical bar download
    via the WebSocket streamer (streamer2.py).
    Caches data in per-exchange Parquet files on remote storage and locally.
    """

    def __init__(self, fs, bucket: str, cache_dir: str = "data"):
        super().__init__(fs, bucket, cache_dir)
        self.supports_live_stream = True
        self._scanner = TradingViewScanner()

    @staticmethod
    def _to_float(value) -> float | None:
        try:
            if value is None:
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _to_int(value) -> int | None:
        try:
            if value is None:
                return None
            return int(float(value))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _to_day_timestamp(ts: int) -> int:
        return ts - (ts % 86400)

    def _build_realtime_candle(
        self,
        symbol: str,
        quote: dict,
        previous: tuple[int, float, float, float, float, float] | None,
    ) -> tuple[int, float, float, float, float, float] | None:
        """Build one OHLCV candle from TradingView quote data.

        Uses quoted bar fields directly when present and keeps per-symbol
        day bucketing stable so downstream code still works with D-based data.
        """
        raw_ts = (
            quote.get("lp_time")
            or quote.get("regular_close_time")
            or quote.get("open_time")
        )

        ts = self._to_int(raw_ts)
        if ts is None:
            if previous is None:
                ts = int(time.time())
            else:
                ts = int(previous[0])

        day_ts = self._to_day_timestamp(ts)
        previous_day_ts = self._to_day_timestamp(previous[0]) if previous else None
        same_day = previous is not None and previous_day_ts == day_ts

        close = self._to_float(quote.get("lp"))
        if close is None:
            close = self._to_float(quote.get("regular_close"))

        open_price = self._to_float(quote.get("open_price"))
        high_price = self._to_float(quote.get("high_price"))
        low_price = self._to_float(quote.get("low_price"))
        volume = self._to_float(quote.get("volume"))

        if same_day:
            prev_open, prev_high, prev_low, prev_close, prev_vol = (
                previous[1],
                previous[2],
                previous[3],
                previous[4],
                previous[5],
            )
            if prev_open is not None:
                open_price = prev_open
            if high_price is not None and prev_high is not None:
                high_price = max(high_price, prev_high)
            else:
                high_price = prev_high if high_price is None else high_price
            if low_price is not None and prev_low is not None:
                low_price = min(low_price, prev_low)
            else:
                low_price = prev_low if low_price is None else low_price
            if close is None:
                close = prev_close
            if volume is None:
                volume = prev_vol
        else:
            if open_price is None:
                if close is None:
                    return None
                open_price = close
            if high_price is None:
                high_price = open_price
            if low_price is None:
                low_price = open_price
            if close is None:
                close = open_price
            if volume is None:
                volume = 0.0

        if (
            open_price is None
            or high_price is None
            or low_price is None
            or close is None
            or volume is None
        ):
            return None

        return (day_ts, open_price, high_price, low_price, close, volume)

    async def refresh_cache(self, symbols: list[str]) -> None:
        """Refreshes the cache by fetching current daily OHLCV from scanner API.

        Splits results by exchange and writes per-exchange Parquet files.
        """
        logger.info("Refreshing TV cache for %d symbols via scanner...", len(symbols))

        ohlcv_data = await self._scanner.fetch_ohlcv()

        if not ohlcv_data:
            logger.warning("No OHLCV data fetched from TradingView scanner.")
            return

        # Build DataFrame from scanner results
        rows = []
        for ticker, candle in ohlcv_data.items():
            timestamp, open_p, high_p, low_p, close_p, volume_p = candle
            rows.append(
                {
                    "timestamp": pd.to_datetime(timestamp, unit="s").floor("D"),
                    "open": open_p,
                    "high": high_p,
                    "low": low_p,
                    "close": close_p,
                    "volume": volume_p,
                    "symbol": ticker,
                }
            )

        if not rows:
            logger.warning("No valid OHLCV rows to save.")
            return

        full_df = pd.DataFrame(rows)
        self.update_cache(full_df, timeframe="1D")
        logger.info("Refreshed cache with %d symbols from scanner.", len(rows))

    async def download_bars(
        self,
        tickers: list[str],
        timeframe: str = "1D",
        bars: int = 1500,
        on_progress: callable = None,
    ) -> int:
        """Downloads full historical bar series for the given tickers via
        the TradingView WebSocket streamer (streamer2.py) and persists
        per-exchange Parquet files.

        Args:
            tickers:     List of TradingView tickers (e.g. ``"NSE:RELIANCE"``).
            timeframe:   TradingView timeframe string (default ``"1D"``).
            on_progress: Optional callback(completed: int, total: int).

        Returns:
            Number of symbols successfully saved.
        """
        from terminal.tradingview.streamer2 import streamer

        logger.info(
            "Downloading bars for %d symbols (timeframe=%s) via WebSocket streamer...",
            len(tickers),
            timeframe,
        )

        rows: list[dict] = []
        completed = 0
        total = len(tickers)

        async for item in streamer.stream_bars(tickers, timeframe=timeframe, bars=bars):
            for ticker, bars in item.items():
                completed += 1
                if not bars:
                    logger.warning("No bars received for %s", ticker)
                    if on_progress:
                        on_progress(completed, total)
                    continue

                for bar in bars:
                    # bar = [timestamp, open, high, low, close, volume]
                    if len(bar) < 6:
                        continue
                    ts, open_p, high_p, low_p, close_p, volume_p = bar[:6]
                    rows.append(
                        {
                            "timestamp": pd.to_datetime(ts, unit="s").floor("D"),
                            "open": float(open_p),
                            "high": float(high_p),
                            "low": float(low_p),
                            "close": float(close_p),
                            "volume": float(volume_p),
                            "symbol": ticker,
                        }
                    )

                logger.debug("  [%d/%d] %s: %d bars", completed, total, ticker, len(bars))
                if on_progress:
                    on_progress(completed, total)

        if not rows:
            logger.warning("No bar data collected — nothing saved.")
            return 0

        df = pd.DataFrame(rows)
        self.update_cache(df, timeframe=timeframe)
        symbol_count = df["symbol"].nunique()
        logger.info("Saved bar data for %d symbols.", symbol_count)
        return symbol_count

    async def download_bars_for_exchange(
        self,
        tickers: list[str],
        exchange: str,
        timeframe: str = "1D",
        bars: int = 1500,
        on_progress: callable = None,
    ) -> int:
        """Download bars for a specific exchange and save to its Parquet file.

        Same as ``download_bars`` but filters tickers to the given exchange
        and writes only that exchange's file.
        """
        exchange_tickers = [
            t for t in tickers if _extract_exchange(t) == exchange
        ]
        if not exchange_tickers:
            logger.warning("No tickers found for exchange %s", exchange)
            return 0

        return await self.download_bars(
            exchange_tickers, timeframe=timeframe, bars=bars, on_progress=on_progress
        )

    async def fetch_live_ohlcv(
        self,
    ) -> dict[str, tuple[int, float, float, float, float, float]]:
        """Fetches current daily OHLCV snapshot from TradingView Scanner API.

        Used by MarketDataManager for polling-based realtime updates.
        """
        return await self._scanner.fetch_ohlcv()

    async def stream_live_ohlcv(
        self, tickers: list[str]
    ) -> AsyncGenerator[
        tuple[str, tuple[int, float, float, float, float, float]], None
    ]:
        """Stream realtime OHLCV updates from TradingView websocket quotes.

        The stream emits one tuple per symbol whenever a new quote tick is
        received:
        (timestamp, open, high, low, close, volume)
        """
        from terminal.tradingview.streamer2 import streamer

        last_candles: dict[str, tuple[int, float, float, float, float, float]] = {}

        async for item in streamer.stream_quotes(tickers):
            if not item:
                continue

            for symbol, quote in item.items():
                if not isinstance(quote, dict):
                    continue

                candle = self._build_realtime_candle(
                    symbol, quote, last_candles.get(symbol)
                )
                if candle is None:
                    continue

                last_candles[symbol] = candle
                yield symbol, candle
