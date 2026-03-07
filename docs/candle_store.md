# Production-Grade Candle Storage — Final Plan

## Storage Layout: Timeframe × Exchange Partitioning

```
{bucket}/market_feed/candles/
├── 1D/
│   ├── NSE.parquet        # 1,500 daily bars × 5,500 symbols
│   ├── BSE.parquet
│   ├── NASDAQ.parquet
│   └── NYSE.parquet
├── 1W/
│   ├── NSE.parquet        # 1,500 weekly bars
│   └── ...
├── 1M/
│   ├── NSE.parquet        # 1,500 monthly bars
│   └── ...
├── 1m/
│   ├── NSE.parquet        # 1,500 one-minute bars
│   └── ...
├── 5m/
│   └── ...
├── 15m/
│   └── ...
└── 1h/
    └── ...
```

- **Each file** holds all symbols for that exchange at that timeframe, max 1,500 bars per symbol
- **Each timeframe** is independently downloadable/refreshable
- **Lazy-loaded** — exchange files loaded on first symbol access, with `asyncio.Lock` per [(timeframe, exchange)](file:///Users/farmaan/Public/farmaan/code/terminal/terminal-data/src/terminal/cli.py#124-136)
- **All data from TradingView** streamer2 (WebSocket bar download)

### Size Estimates (1,500 bars)

| Timeframe | NSE (5.5K sym) | NASDAQ (5K sym) | Total All Exchanges |
|-----------|---------------|----------------|---------------------|
| 1D | ~60MB | ~55MB | ~200MB |
| 1W | ~60MB | ~55MB | ~200MB |
| 1M | ~40MB | ~35MB | ~130MB |
| 1m | ~60MB | ~55MB | ~200MB |
| **All** | | | **~900MB–1.2GB** |

---

## Proposed Changes

### Phase 1: Partitioned Storage + Lazy Loading

---

#### [MODIFY] [provider.py](file:///Users/farmaan/Public/farmaan/code/terminal/terminal-data/src/terminal/market_feed/provider.py)

Rewrite [DataProvider](file:///Users/farmaan/Public/farmaan/code/terminal/terminal-data/src/terminal/market_feed/provider.py#12-141) for timeframe × exchange partitioned storage:

```python
class PartitionedProvider:
    """Exchange-partitioned Parquet storage with lazy loading."""

    def __init__(self, fs, bucket, cache_dir="data"):
        self._fs = fs
        self._bucket = bucket
        self._cache_dir = Path(cache_dir)
        # Loaded data: {(timeframe, exchange): {symbol: DataFrame}}
        self._data: dict[tuple[str,str], dict[str, pd.DataFrame]] = {}
        # Per-(timeframe, exchange) locks for lazy loading
        self._locks: dict[tuple[str,str], asyncio.Lock] = {}

    def _remote_path(self, timeframe: str, exchange: str) -> str:
        return f"{self._bucket}/market_feed/candles/{timeframe}/{exchange}.parquet"

    def _local_path(self, timeframe: str, exchange: str) -> Path:
        d = self._cache_dir / "candles" / timeframe
        d.mkdir(parents=True, exist_ok=True)
        return d / f"{exchange}.parquet"

    async def ensure_loaded(self, timeframe: str, exchange: str):
        """Lazy-load with lock — safe for concurrent access."""
        key = (timeframe, exchange)
        if key in self._data:
            return
        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:
            if key in self._data:  # double-check after lock
                return
            self._load_exchange(timeframe, exchange)

    def get_history(self, symbol: str, timeframe: str = "1D") -> pd.DataFrame | None:
        exchange = symbol.split(":")[0] if ":" in symbol else "NSE"
        key = (timeframe, exchange)
        return self._data.get(key, {}).get(symbol)
```

#### [MODIFY] [store.py](file:///Users/farmaan/Public/farmaan/code/terminal/terminal-data/src/terminal/market_feed/store.py)

- `int32` → `int64` timestamps
- **Multi-timeframe support**: change internal keys from [symbol](file:///Users/farmaan/Public/farmaan/code/terminal/terminal-data/src/terminal/market_feed/store.py#137-140) → [(symbol, timeframe)](file:///Users/farmaan/Public/farmaan/code/terminal/terminal-data/src/terminal/cli.py#124-136) composite key. All stores (`_timestamps`, [_ohlcv](file:///Users/farmaan/Public/farmaan/code/terminal/terminal-data/src/terminal/market_feed/manager.py#347-394), `_sizes`, `_locks`) keyed by [(symbol, timeframe)](file:///Users/farmaan/Public/farmaan/code/terminal/terminal-data/src/terminal/cli.py#124-136) tuple so the same symbol can hold data at different resolutions simultaneously
- [get_data(symbol, timeframe="1D")](file:///Users/farmaan/Public/farmaan/code/terminal/terminal-data/src/terminal/market_feed/store.py#109-127), [load_history(symbol, timeframe, df)](file:///Users/farmaan/Public/farmaan/code/terminal/terminal-data/src/terminal/market_feed/store.py#44-73), [add_realtime(symbol, timeframe, candle)](file:///Users/farmaan/Public/farmaan/code/terminal/terminal-data/src/terminal/market_feed/store.py#74-108)
- Keep existing ring buffer design (it works well for realtime cache)

#### [MODIFY] [manager.py](file:///Users/farmaan/Public/farmaan/code/terminal/terminal-data/src/terminal/market_feed/manager.py)

- Startup: no eager loading — all exchanges lazy-loaded
- [get_ohlcv()](file:///Users/farmaan/Public/farmaan/code/terminal/terminal-data/src/terminal/market_feed/manager.py#347-394): call `provider.ensure_loaded()` before accessing store
- Remove shutdown cache flush (realtime is ephemeral, daily Parquet is source of truth)

#### [MODIFY] [tradingview.py](file:///Users/farmaan/Public/farmaan/code/terminal/terminal-data/src/terminal/market_feed/tradingview.py)

- [download_bars(exchange, timeframe, bar_count=1500)](file:///Users/farmaan/Public/farmaan/code/terminal/terminal-data/src/terminal/market_feed/tradingview.py#167-236) — download via streamer2 and write per-exchange Parquet
- `refresh_exchange(exchange, timeframe)` — re-download full history for one exchange at one timeframe

#### [MODIFY] [main.py](file:///Users/farmaan/Public/farmaan/code/terminal/terminal-data/src/terminal/main.py)

- Remove dirty-cache flush on shutdown
- Startup: initialize provider but don't load any data (lazy)

#### [MODIFY] [cli.py](file:///Users/farmaan/Public/farmaan/code/terminal/terminal-data/src/terminal/cli.py)

```bash
# Download 1,500 daily bars for NSE
terminal market-data download-bars --exchange NSE --timeframe 1D --bars 1500

# Download all timeframes for an exchange
terminal market-data download-bars --exchange NSE --timeframe all

# Refresh all exchanges for daily
terminal market-data refresh-daily --exchange all
```

---

### Phase 2: APScheduler + Admin Dashboard

---

#### [NEW] [scheduler.py](file:///Users/farmaan/Public/farmaan/code/terminal/terminal-data/src/terminal/market_feed/scheduler.py)

APScheduler-based refresh scheduler:

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

REFRESH_SCHEDULE = {
    "NSE":    {"cron": "15 16 * * 1-5", "tz": "Asia/Kolkata"},
    "BSE":    {"cron": "15 16 * * 1-5", "tz": "Asia/Kolkata"},
    "NASDAQ": {"cron": "30 16 * * 1-5", "tz": "America/New_York"},
    "NYSE":   {"cron": "30 16 * * 1-5", "tz": "America/New_York"},
}

TIMEFRAMES = ["1D", "1W", "1M"]  # expand as needed
```

- Uses `APScheduler` for reliable cron-like scheduling
- Each job: download full history for (exchange, timeframe) → atomic swap (write temp file, rename)
- Job status tracked in DB table `candle_data_refreshes`:

```sql
CREATE TABLE candle_data_refreshes (
    id SERIAL PRIMARY KEY,
    exchange VARCHAR(10) NOT NULL,
    timeframe VARCHAR(5) NOT NULL,
    status VARCHAR(20) NOT NULL,   -- pending | running | success | failed
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    symbols_count INT,
    error_message TEXT,
    duration_seconds FLOAT
);
```

#### [NEW] [scheduler router](file:///Users/farmaan/Public/farmaan/code/terminal/terminal-data/src/terminal/market_feed/scheduler_router.py)

Admin API endpoints:
- `GET /api/v1/admin/refreshes` — list recent refresh runs with status
- `POST /api/v1/admin/refreshes/{exchange}/{timeframe}` — trigger manual refresh
- `GET /api/v1/admin/refreshes/schedule` — view upcoming scheduled refreshes

---

### Phase 3: Zero-Downtime Deployment

#### [MODIFY] [docker-compose.yaml](file:///Users/farmaan/Public/farmaan/code/terminal/terminal-data/docker-compose.yaml)

- `stop_grace_period: 30s`
- Health check with startup probe

---

## Verification Plan

### Automated Tests
- `PartitionedProvider`: load/save per-exchange files, lazy loading with concurrent access
- `scheduler.py`: job execution, status tracking, error handling
- CLI commands: download-bars, refresh integration

### Manual Verification
- `terminal market-data download-bars --exchange NSE --timeframe 1D --bars 1500`
- Verify Parquet files created at correct paths in OCI
- Restart app → verify lazy loading works (no data loaded until first query)
- Trigger refresh via admin API → verify job status updates
