# Terminal Data Backend Architecture

## System Overview
The Terminal Data Backend is a Python-based system designed to provide financial data, run technical scans, and manage real-time alerts for stock markets (primarily India and US). It aggregates data from multiple sources, processes it using a custom scanning engine, and exposes APIs for clients.

## High-Level Architecture
The system is built around a modular architecture with distinct responsibilities:
- **Data Ingestion**: Fetching data from external providers (TradingView, MarketSmith, StockTwits).
- **Processing Engine**:
  - **EzScan**: A vectorized technical analysis engine for scanning markets.
  - **Alerts**: A real-time engine for monitoring price conditions.
- **Storage/Caching**: utilizing OCI (Oracle Cloud Infrastructure) Object Storage for persisting heavy data (metadata, fundamentals) and in-memory caching for performance.
- **API Layer**: FastAPI-based REST and WebSocket interfaces.

## Key Modules

### 1. EzScan (`modules/ezscan`)
The core scanning engine responsible for filtering stocks based on technical and fundamental criteria.
- **ScannerEngine**: Orchestrates the scanning process. It handles data loading, caching, and executes scans in two phases (PreScan and Main Scan).
- **ExpressionEvaluator**: A custom expression parser that evaluates technical indicators (SMA, EMA, RSI, etc.) and logical conditions against market data. It supports vectorized operations for high performance.
- **Data Providers**:
  - `TradingViewCandleProvider`: Fetches historical OHLCV data from TradingView. Supports both "india" and "us" markets. Caches data to local pickle files (`ohlcv_india.pkl`, `ohlcv_us.pkl`).
  - `YahooCandleProvider`: Alternative provider fetching data from Yahoo Finance.
  - `IndiaMetadataProvider`: Loads symbol metadata for Indian stocks from `symbols-full-v2.parquet` stored in OCI.
  - `USMetadataProvider`: Loads symbol metadata for US stocks from `us-symbols.parquet` stored in OCI.
- **Models**: Defines `ScanRequest` and `ScanResponse` APIs, allowing client-defined logic (`conditions`, `columns`, `sort`).

### 2. Alerts System (`modules/alerts`)
A system for real-time monitoring of stock prices against user-defined conditions.
- **AlertEngine**: The main loop that manages the lifecycle of alerts. It synchronizes active alerts from storage and subscribes to real-time data.
- **AlertManager**: Manages the in-memory state of active alerts, organizing them by symbol for efficient evaluation.
- **Evaluator**: Evaluates specific alert conditions (e.g., "Price > 100", "Price crosses Trendline") against live price updates.
- **NotificationDispatcher**: Queues and dispatches notifications when alerts trigger.
- **Real-time Data**: Uses `TradingViewProvider` to receive live price ticks via WebSocket.

### 3. Core Providers (`modules/core/provider`)
Modules handling communication with external data sources.
- **TradingView**:
  - `TradingView`: Helper class for HTTP/WebSocket interactions.
  - `TradingViewProvider` (in alerts): Manages WebSocket connections for real-time price feeds.
  - `TradingViewCandleProvider` (in ezscan): Fetches historical candle data.
- **MarketSmith**:
  - `MarketSmithClient`: Async client for fetching fundamental data, broker estimates, and bulk/block deals from MarketSmith India.
- **StockTwits**:
  - `StockTwitsClient`: Fetches social sentiment data (trending/popular streams).

### 4. API Layer (`modules/api`)
Exposes functionality to the outside world.
- **REST Endpoints**:
  - `/scanner/scan` & `/v2/scan`: Execute technical scans.
  - `/symbols/{symbol}`: Get detailed symbol info (via MarketSmith).
  - `/ideas/...`: Get social sentiment feeds (via StockTwits).
- **WebSocket**:
  - `/ws`: Real-time communication (likely for pushing alert notifications or scan updates).
- **Scheduler**: Uses `APScheduler` for periodic background tasks like data refreshing and cache warming.

### 5. Utilities (`utils/`)
Shared helper functions and configurations.
- **Storage**: `bucket.py` configures `ocifs` for interactions with OCI Object Storage.
- **Fundamentals**: `fundamentals.py` handles fetching and caching of fundamental financial data.
- **Compliance**: `compliant.py` fetches and parses Shariah compliance data.

## Data Flow

### Scanning Flow
1. **Request**: Client sends a `ScanRequest` with conditions (e.g., `close > sma(20)`) and desired columns.
2. **Parsing**: `ScannerEngine` parses the request.
3. **Pre-Scan**: Rapidly filters symbols using lightweight checks (if configured).
4. **Evaluation**: `ExpressionEvaluator` fetches cached OHLCV data and metadata, then evaluates the logic vectorially across all symbols using `pandas`/`numpy`.
5. **Response**: Returns a JSON structure with filtered symbols and requested data columns.

### Alerting Flow
1. **Setup**: `AlertEngine` loads active alerts from storage on startup.
2. **Subscription**: Subscribes to real-time price updates for relevant symbols via `TradingViewProvider`.
3. **Event Loop**:
   - Packet received -> `ChangeUpdate` created.
   - `AlertManager` identifies alerts for the symbol.
   - `Evaluator` checks conditions.
   - If triggered: Alert is marked triggered in store, removed from manager, and sent to `NotificationDispatcher`.

### Data Refresh
- Background jobs (via `APScheduler`) periodically run scripts to:
  - Download new fundamental data.
  - Refresh Shariah compliance lists.
  - Update cached Parquet files in OCI.

## Technology Stack
- **Language**: Python 3.10+
- **Web Framework**: FastAPI
- **Data Processing**: Pandas, NumPy
- **Storage**: OCI Object Storage (Parquet/JSON)
- **Scheduling**: APScheduler
- **Networking**: Httpx, Websockets, CloudScraper (StockTwits)

## Supported Technical Indicators
The `ExpressionEvaluator` supports a custom expression language with the following built-in functions:
- **Trend**: `sma(source, window)`, `ema(source, window)`
- **Momentum**: `change(source, periods)`
- **Rolling Stats**: `min(source, window)`, `max(source, window)`, `count(source, window)`, `countTrue(condition, window)`
- **Accessors**: `c` (Close), `o` (Open), `h` (High), `l` (Low), `v` (Volume), `prv(source, offset)`

## Configuration & Deployment
- **Environment**: Managed via `.env` file (loaded by `python-dotenv`). Key variables include:
  - `OCI_CONFIG`, `OCI_KEY`, `OCI_BUCKET`: Oracle Cloud Object Storage credentials.
  - `STOCK_FUNDAMENTAL_BASE_URL`: API endpoint for fundamental data.
- **Entry Point**: `main.py` serves as the CLI entry point with modes:
  - `api`: Starts the FastAPI server.
  - `scan`: Runs a one-off scan.
  - `alerts`: Starts the alert worker.
  - `download-*`: Data fetching utilities.
- **Docker**: The application is containerized (see `Dockerfile` and `docker-compose.yaml`), using `uv` for dependency management.
