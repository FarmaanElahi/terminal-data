# Production-Grade Terminal: Comprehensive Improvement Plan

## Implementation Summary

All 6 workstreams implemented across 5 phases.

### Workstream 1: Real-Time Candle Aggregation
- **New**: `src/terminal/candles/aggregator.py` — `CandleAggregator` class that consumes 1-min WebSocket candles and produces higher timeframes (3m, 5m, 15m, 30m, 1h, 2h, 4h) via on-the-fly aggregation
- **Modified**: `src/terminal/candles/service.py` — wired aggregator into CandleManager with `subscribe_aggregated()` / `unsubscribe_aggregated()` methods and background dispatch loop
- **Modified**: `src/terminal/realtime/chart.py` — ChartSession `_stream_loop` now routes non-passthrough intervals through aggregator

### Workstream 2: Data Ingestion Resilience
- **New**: `src/terminal/infra/circuit_breaker.py` — generic async circuit breaker (CLOSED/OPEN/HALF_OPEN states) + `retry_with_backoff()` utility
- **Modified**: `src/terminal/tradingview/scanner.py` — retry with backoff on `fetch_ohlcv()`, shorter 10s timeout, retryable error classification
- **Modified**: `src/terminal/market_feed/manager.py` — scanner polls wrapped with circuit breaker, staleness tracking (`_last_successful_poll`, `_consecutive_failures`)
- **Modified**: `src/terminal/market_feed/provider.py` — OCI sync retry (3 attempts) with fallback to local cache

### Workstream 3: Screener Reliability
- **Modified**: `src/terminal/realtime/screener.py`:
  - Formula error reporting via `ScreenerErrorsResponse` (parse + runtime errors)
  - Shared `ScreenerCache` with ref-counting for sessions with identical params
  - Periodic metadata refresh (every 5 minutes)
  - Evaluation throttling: `_MAX_SYMBOLS_PER_CYCLE=5000`, `_MAX_CONDITIONS=50`
- **Modified**: `src/terminal/realtime/models.py` — added `ScreenerErrorInfo` and `ScreenerErrorsResponse` models

### Workstream 4: Infrastructure & Observability
- **New**: `src/terminal/health/router.py` — `GET /health` (liveness) + `GET /ready` (readiness with DB/MarketData/CandleFeed checks)
- **New**: `src/terminal/middleware.py` — `RequestLoggingMiddleware` with request_id (UUID), duration tracking, `X-Request-ID` header, error handling
- **Modified**: `src/terminal/logging.py` — `JSONFormatter` for structured logging, configurable via `LOG_FORMAT` env var
- **Modified**: `src/terminal/main.py`:
  - CORS middleware (permissive in dev, restrictive in prod)
  - Request logging middleware
  - Graceful shutdown: close WS connections → stop polling → flush cache → close feeds
- **Modified**: `src/terminal/realtime/handler.py` — `ConnectionManager` with max 500 total / 5 per-user connection limits, `close_all()` for shutdown

### Workstream 5: Database & Auth Hardening
- **Modified**: `src/terminal/database/core.py` — connection pooling: `pool_size=10`, `max_overflow=20`, `pool_pre_ping=True`, `pool_recycle=3600`, 30s statement timeout, conditional echo
- **Modified**: `src/terminal/config.py` — `environment` + `log_format` settings, `secret_key` production validation, `min_password_length`
- **Modified**: `src/terminal/auth/router.py` — in-memory rate limiting on login (5 attempts/60s per IP)
- **Modified**: `src/terminal/auth/models.py` — password minimum length validation

### Workstream 6: Deployment & Operations
- **New**: `Dockerfile` — multi-stage build (builder + slim runtime), non-root user, health check
- **New**: `docker-compose.prod.yaml` — postgres + backend with health checks, resource limits, restart policies
- **Modified**: `src/terminal/cli.py`:
  - `terminal health` — CLI health check (DB, OCI, TradingView)
  - `terminal database backup` / `terminal database restore`
  - `terminal market-data validate` — cache integrity validation

## Files Created
- `src/terminal/health/__init__.py`
- `src/terminal/health/router.py`
- `src/terminal/infra/__init__.py`
- `src/terminal/infra/circuit_breaker.py`
- `src/terminal/middleware.py`
- `src/terminal/candles/aggregator.py`
- `Dockerfile`
- `docker-compose.prod.yaml`

## Files Modified
- `src/terminal/main.py`
- `src/terminal/api.py` (no change needed — health router mounted on top-level app)
- `src/terminal/config.py`
- `src/terminal/logging.py`
- `src/terminal/database/core.py`
- `src/terminal/market_feed/manager.py`
- `src/terminal/market_feed/provider.py`
- `src/terminal/tradingview/scanner.py`
- `src/terminal/candles/service.py`
- `src/terminal/realtime/handler.py`
- `src/terminal/realtime/chart.py`
- `src/terminal/realtime/screener.py`
- `src/terminal/realtime/models.py`
- `src/terminal/auth/router.py`
- `src/terminal/auth/models.py`
- `src/terminal/cli.py`

## Decisions
- No Redis — all in-memory, single-instance
- JSON structured logging via `LOG_FORMAT=json` env var
- Aggregator supports any timeframe dynamically
- Health checks at root level (`/health`, `/ready`), not under `/api/v1`
