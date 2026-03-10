"""Exchange-partitioned Parquet storage with lazy loading.

Storage layout::

    {bucket}/market_feed/candles/{timeframe}/{exchange}.parquet

Each Parquet file contains all symbols for one exchange at one timeframe,
with a maximum of ``MAX_BARS`` rows per symbol.

Files are loaded lazily on first access, with ``asyncio.Lock`` per
``(timeframe, exchange)`` to prevent duplicate loads under concurrency.
"""

import asyncio
import json
import logging
from pathlib import Path

import pandas as pd
from fsspec import AbstractFileSystem

logger = logging.getLogger(__name__)

MAX_BARS = 1500

# Known exchanges and their canonical names
EXCHANGES = ("NSE", "BSE", "NASDAQ", "NYSE", "AMEX")

# Standard timeframes supported
TIMEFRAMES = ("1D", "1W", "1M")


def _extract_exchange(symbol: str) -> str:
    """Extract exchange prefix from a ticker like ``NSE:RELIANCE``."""
    return symbol.split(":")[0] if ":" in symbol else "NSE"


class PartitionedProvider:
    """Exchange-partitioned Parquet provider with lazy loading.

    Data is organised as one Parquet file per ``(timeframe, exchange)`` pair.
    Files are synced between a remote filesystem (e.g. OCI Object Storage)
    and a local cache directory.
    """

    def __init__(
        self,
        fs: AbstractFileSystem,
        bucket: str,
        cache_dir: str = "data",
    ):
        self.fs = fs
        self.bucket = bucket
        self.cache_dir = Path(cache_dir) / "candles"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.supports_live_stream = True

        # Loaded data: {(timeframe, exchange): {symbol: DataFrame}}
        self._data: dict[tuple[str, str], dict[str, pd.DataFrame]] = {}

        # Per-(timeframe, exchange) locks for lazy loading
        self._locks: dict[tuple[str, str], asyncio.Lock] = {}

        # ETag cache: {(timeframe, exchange): etag_string}
        self._etags: dict[tuple[str, str], str] = {}
        self._load_etags()

    # ------------------------------------------------------------------
    # Path helpers
    # ------------------------------------------------------------------

    def _remote_path(self, timeframe: str, exchange: str) -> str:
        return f"{self.bucket}/market_feed/candles/{timeframe}/{exchange}.parquet"

    def _local_path(self, timeframe: str, exchange: str) -> Path:
        d = self.cache_dir / timeframe
        d.mkdir(parents=True, exist_ok=True)
        return d / f"{exchange}.parquet"

    def _etag_file(self) -> Path:
        return self.cache_dir / "_etags.json"

    def _load_etags(self) -> None:
        """Load persisted ETags from disk."""
        path = self._etag_file()
        if path.exists():
            try:
                data = json.loads(path.read_text())
                for k, v in data.items():
                    parts = k.split("|", 1)
                    if len(parts) == 2:
                        self._etags[(parts[0], parts[1])] = v
            except Exception:
                logger.warning("Failed to load ETag cache, starting fresh")

    def _save_etags(self) -> None:
        """Persist ETags to disk."""
        data = {f"{tf}|{ex}": etag for (tf, ex), etag in self._etags.items()}
        try:
            self._etag_file().write_text(json.dumps(data))
        except Exception:
            logger.warning("Failed to persist ETag cache")

    # ------------------------------------------------------------------
    # Lazy loading
    # ------------------------------------------------------------------

    async def ensure_loaded(self, timeframe: str, exchange: str) -> None:
        """Lazy-load an exchange file with lock — safe for concurrent access."""
        key = (timeframe, exchange)
        if key in self._data:
            return

        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:
            if key in self._data:  # double-check after acquiring lock
                return
            await asyncio.to_thread(self._load_exchange, timeframe, exchange)

    async def reload_exchange(self, timeframe: str, exchange: str) -> None:
        """Conditionally re-sync from remote if the ETag has changed.

        Compares the remote file's ETag against our cached ETag.
        If they match, skips the download and just ensures the data is
        loaded in memory.  If they differ (or we have no cached ETag),
        downloads and re-parses.
        """
        key = (timeframe, exchange)
        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:
            changed = await asyncio.to_thread(
                self._check_and_sync, timeframe, exchange
            )
            if changed or key not in self._data:
                await asyncio.to_thread(self._load_exchange, timeframe, exchange)
                logger.info(
                    "Reloaded %s/%s (data changed on remote)",
                    timeframe, exchange,
                )
            else:
                logger.debug(
                    "Skipped reload for %s/%s (ETag unchanged)",
                    timeframe, exchange,
                )

    def _check_and_sync(self, timeframe: str, exchange: str) -> bool:
        """Check remote ETag; download only if changed.

        Returns True if data was downloaded (i.e. changed), False otherwise.
        """
        key = (timeframe, exchange)
        remote = self._remote_path(timeframe, exchange)

        try:
            if not self.fs.exists(remote):
                logger.info("Remote file does not exist: %s", remote)
                return False

            info = self.fs.info(remote)
            remote_etag = info.get("ETag") or info.get("etag") or ""
            # Fall back to size + mtime as a pseudo-ETag
            if not remote_etag:
                size = info.get("size", 0)
                mtime = info.get("mtime") or info.get("LastModified") or ""
                remote_etag = f"{size}:{mtime}"

            cached_etag = self._etags.get(key)

            if cached_etag and cached_etag == remote_etag:
                return False  # No change

            # ETag differs — download
            self._sync_from_remote(timeframe, exchange)
            self._etags[key] = remote_etag
            self._save_etags()
            return True

        except Exception as e:
            logger.warning(
                "ETag check failed for %s/%s: %s — falling back to full sync",
                timeframe, exchange, e,
            )
            self._sync_from_remote(timeframe, exchange)
            return True

    def _load_exchange(self, timeframe: str, exchange: str) -> None:
        """Load one exchange file from local cache (sync from remote if needed)."""
        key = (timeframe, exchange)
        local = self._local_path(timeframe, exchange)

        if not local.exists():
            self._sync_from_remote(timeframe, exchange)

        if not local.exists():
            logger.info(
                "No data found for %s/%s (local and remote empty)", timeframe, exchange
            )
            self._data[key] = {}
            return

        try:
            df = pd.read_parquet(local)
            if df.empty:
                self._data[key] = {}
                return

            symbols: dict[str, pd.DataFrame] = {}
            for symbol, group in df.groupby("symbol"):
                hist = group[
                    ["timestamp", "open", "high", "low", "close", "volume"]
                ].copy()

                # Convert timestamp to int64 seconds
                if pd.api.types.is_datetime64_any_dtype(hist["timestamp"]):
                    hist["timestamp"] = (
                        hist["timestamp"]
                        .values.astype("datetime64[s]")
                        .astype("int64")
                    )
                else:
                    hist["timestamp"] = hist["timestamp"].astype("int64")

                # Downcast OHLCV to float32
                for col in ("open", "high", "low", "close", "volume"):
                    hist[col] = hist[col].astype("float32")

                hist = hist.sort_values("timestamp")
                hist = hist.set_index("timestamp")

                # Limit to MAX_BARS most recent bars
                if len(hist) > MAX_BARS:
                    hist = hist.iloc[-MAX_BARS:]

                symbols[str(symbol)] = hist

            self._data[key] = symbols
            logger.info(
                "Loaded %d symbols for %s/%s from cache",
                len(symbols),
                timeframe,
                exchange,
            )
        except Exception:
            logger.exception("Error loading %s/%s from local cache", timeframe, exchange)
            self._data[key] = {}

    def _sync_from_remote(self, timeframe: str, exchange: str) -> None:
        """Download a remote Parquet file to local cache atomically.
        
        Downloads to a .tmp file first and only replaces the local cache
        if the download completes successfully and the file is non-empty.
        """
        remote = self._remote_path(timeframe, exchange)
        local = self._local_path(timeframe, exchange)
        tmp = local.with_suffix(".parquet.tmp")
        max_retries = 3

        for attempt in range(max_retries):
            try:
                if not self.fs.exists(remote):
                    logger.info("Remote file does not exist: %s", remote)
                    return

                # Download to temporary file
                self.fs.get(remote, str(tmp))
                
                # Verify download: exists and size > 0
                if tmp.exists() and tmp.stat().st_size > 0:
                    # Atomic replacement
                    tmp.replace(local)
                    logger.info("Synced from remote: %s", remote)
                    return
                else:
                    logger.warning(
                        "Download failed for %s: temporary file %s is empty or missing",
                        remote, tmp
                    )
                    if tmp.exists():
                        tmp.unlink()
            except Exception as e:
                logger.warning(
                    "Remote sync attempt %d/%d failed for %s: %s",
                    attempt + 1,
                    max_retries,
                    remote,
                    e,
                )
                if tmp.exists():
                    tmp.unlink()
                
                if attempt == max_retries - 1:
                    if local.exists():
                        logger.warning(
                            "Remote unreachable after %d retries — using local cache for %s/%s",
                            max_retries,
                            timeframe,
                            exchange,
                        )
                    else:
                        logger.error(
                            "Remote unreachable and no local cache for %s/%s",
                            timeframe,
                            exchange,
                        )

    # ------------------------------------------------------------------
    # Data access
    # ------------------------------------------------------------------

    def get_history(
        self, symbol: str, timeframe: str = "1D"
    ) -> pd.DataFrame | None:
        """Retrieve historical data for a symbol at a timeframe.

        Returns ``None`` if the exchange file has not been loaded yet
        or the symbol is not found.  Callers should ``await ensure_loaded()``
        first.
        """
        exchange = _extract_exchange(symbol)
        key = (timeframe, exchange)
        return self._data.get(key, {}).get(symbol)

    def get_all_tickers(self, timeframe: str = "1D") -> list[str]:
        """Return all tickers loaded across all exchanges for a timeframe."""
        tickers: list[str] = []
        for (tf, _ex), symbols in self._data.items():
            if tf == timeframe:
                tickers.extend(symbols.keys())
        return tickers

    def get_loaded_exchanges(self, timeframe: str = "1D") -> list[str]:
        """Return exchanges that have been loaded for a timeframe."""
        return [ex for (tf, ex) in self._data if tf == timeframe]

    # ------------------------------------------------------------------
    # Writing
    # ------------------------------------------------------------------

    def save_exchange(
        self,
        timeframe: str,
        exchange: str,
        data: dict[str, pd.DataFrame],
    ) -> None:
        """Persist data for one exchange at one timeframe.

        Uses atomic write (write to temp, rename) to prevent corruption.

        Args:
            timeframe: e.g. ``"1D"``, ``"1m"``
            exchange: e.g. ``"NSE"``, ``"NASDAQ"``
            data: mapping of symbol → DataFrame with OHLCV columns and
                  timestamp index
        """
        if not data:
            logger.warning("No data to save for %s/%s", timeframe, exchange)
            return

        # Build combined DataFrame
        dfs: list[pd.DataFrame] = []
        for symbol, df in data.items():
            if df is None or len(df) == 0:
                continue
            df_copy = df.copy()
            df_copy["symbol"] = symbol
            df_copy.reset_index(inplace=True)
            dfs.append(df_copy)

        if not dfs:
            return

        full_df = pd.concat(dfs, ignore_index=True)

        local = self._local_path(timeframe, exchange)
        tmp = local.with_suffix(".parquet.tmp")

        try:
            # Atomic write: temp file → rename
            full_df.to_parquet(tmp, index=False, compression="zstd")
            tmp.rename(local)

            # Upload to remote
            remote = self._remote_path(timeframe, exchange)
            self.fs.put(str(local), remote)
            logger.info(
                "Saved %d symbols for %s/%s to remote",
                len(data),
                timeframe,
                exchange,
            )
        except Exception:
            logger.exception("Failed to save %s/%s", timeframe, exchange)
            # Clean up temp file
            if tmp.exists():
                tmp.unlink()

    def update_exchange_in_memory(
        self,
        timeframe: str,
        exchange: str,
        data: dict[str, pd.DataFrame],
    ) -> None:
        """Update the in-memory cache for an exchange without writing to disk."""
        key = (timeframe, exchange)
        self._data[key] = data

    # ------------------------------------------------------------------
    # Backward compatibility helpers
    # ------------------------------------------------------------------

    def update_cache(self, df: pd.DataFrame, timeframe: str = "1D") -> None:
        """Persist data from a combined DataFrame, splitting by exchange.

        This provides backward compatibility with the old monolithic cache
        approach.  The DataFrame must contain a ``symbol`` column with
        ``EXCHANGE:TICKER`` formatted values.
        """
        if df.empty:
            return

        # Group by exchange
        df = df.copy()
        df["_exchange"] = df["symbol"].apply(_extract_exchange)

        for exchange, group in df.groupby("_exchange"):
            symbols: dict[str, pd.DataFrame] = {}
            for symbol, sym_group in group.groupby("symbol"):
                hist = sym_group[
                    ["timestamp", "open", "high", "low", "close", "volume"]
                ].copy()

                if pd.api.types.is_datetime64_any_dtype(hist["timestamp"]):
                    hist["timestamp"] = (
                        hist["timestamp"]
                        .values.astype("datetime64[s]")
                        .astype("int64")
                    )
                else:
                    hist["timestamp"] = hist["timestamp"].astype("int64")

                for col in ("open", "high", "low", "close", "volume"):
                    hist[col] = hist[col].astype("float32")

                hist = hist.sort_values("timestamp").set_index("timestamp")

                if len(hist) > MAX_BARS:
                    hist = hist.iloc[-MAX_BARS:]

                symbols[str(symbol)] = hist

            self.save_exchange(timeframe, str(exchange), symbols)
            self.update_exchange_in_memory(timeframe, str(exchange), symbols)

        logger.info(
            "Updated cache for %d exchanges at timeframe %s",
            df["_exchange"].nunique(),
            timeframe,
        )
