import logging
import pandas as pd

from .provider import DataProvider

from terminal.tradingview.scanner import TradingViewScanner

logger = logging.getLogger(__name__)


class TradingViewDataProvider(DataProvider):
    """
    DataProvider that fetches daily OHLCV data from TradingView Scanner API.
    Uses polling instead of WebSocket streaming for reliability.
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

    async def fetch_live_ohlcv(
        self,
    ) -> dict[str, tuple[int, float, float, float, float, float]]:
        """
        Fetches current daily OHLCV snapshot from TradingView Scanner API.
        Used by MarketDataManager for polling-based realtime updates.
        """
        return await self._scanner.fetch_ohlcv()
