import logging
import pandas as pd

from .provider import DataProvider

from terminal.tradingview.scanner import TradingViewScanner

logger = logging.getLogger(__name__)


class TradingViewDataProvider(DataProvider):
    """
    DataProvider that fetches daily OHLCV data from TradingView.
    Supports both a Scanner REST API snapshot and full historical bar download
    via the WebSocket streamer (streamer2.py).
    Caches data in OCI Object Storage and locally in Parquet format.
    """

    def __init__(self, fs: any, bucket: str, cache_dir: str = "data"):
        super().__init__(fs, bucket, cache_dir, provider_name="tv")
        self._scanner = TradingViewScanner()

    async def refresh_cache(self, symbols: list[str]):
        """Refreshes the cache by fetching current daily OHLCV from scanner API."""
        logger.info(f"Refreshing TV cache for {len(symbols)} symbols via scanner...")

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
        self.update_cache(full_df)
        logger.info(f"Refreshed cache with {len(rows)} symbols from scanner.")

    async def download_bars(
        self,
        tickers: list[str],
        timeframe: str = "1D",
        on_progress: callable = None,
    ) -> int:
        """
        Downloads full historical bar series for the given tickers via
        the TradingView WebSocket streamer (streamer2.py) and persists
        the result to local Parquet + OCI.

        Args:
            tickers:     List of TradingView tickers (e.g. ``"NSE:RELIANCE"``).
            timeframe:   TradingView timeframe string (default ``"1D"``).
            on_progress: Optional callback(completed: int, total: int) for progress.

        Returns:
            Number of symbols successfully saved.
        """
        from terminal.tradingview.streamer2 import streamer

        logger.info(
            f"Downloading bars for {len(tickers)} symbols "
            f"(timeframe={timeframe}) via WebSocket streamer..."
        )

        rows = []
        completed = 0
        total = len(tickers)

        async for item in streamer.stream_bars(tickers, timeframe=timeframe):
            for ticker, bars in item.items():
                completed += 1
                if not bars:
                    logger.warning(f"No bars received for {ticker}")
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

                logger.debug(f"  [{completed}/{total}] {ticker}: {len(bars)} bars")
                if on_progress:
                    on_progress(completed, total)

        if not rows:
            logger.warning("No bar data collected — nothing saved.")
            return 0

        df = pd.DataFrame(rows)
        self.update_cache(df)
        symbol_count = df["symbol"].nunique()
        logger.info(f"Saved bar data for {symbol_count} symbols to OCIFS.")
        return symbol_count

    async def fetch_live_ohlcv(
        self,
    ) -> dict[str, tuple[int, float, float, float, float, float]]:
        """
        Fetches current daily OHLCV snapshot from TradingView Scanner API.
        Used by MarketDataManager for polling-based realtime updates.
        """
        return await self._scanner.fetch_ohlcv()
