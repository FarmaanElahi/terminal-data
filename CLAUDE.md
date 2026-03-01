# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Architecture Overview

This is a stock market terminal with two main parts:

- **Backend** (`src/terminal/`): FastAPI server (Python 3.13, managed with `uv`) serving REST and WebSocket APIs. It connects to PostgreSQL, OCI object storage (for cached market data), TradingView (market data source), and Upstox (Indian market candles via WebSocket).
- **Frontend** (`src/web/`): React 19 + TypeScript SPA with Vite, Tailwind CSS v4, shadcn/ui, Zustand for state, and TanStack Query/Table/Virtual for data fetching and virtualized tables.

**Design system**: See [`docs/design-system.md`](docs/design-system.md) for the full design philosophy, color tokens, typography, spacing, animation, and component conventions. Always follow this document when building UI.

### Frontend Module Map (`src/web/src/`)

| Path | Responsibility |
| ---- | -------------- |
| `main.tsx` | Entry point — renders `<App />` |
| `styles/globals.css` | All CSS custom properties (OKLCH color tokens, fonts, animations, scrollbar utilities) |
| `app/providers.tsx` | Wraps app with React Query, Router, Auth, and Theme providers |
| `app/routes.tsx` | Route definitions — maps paths to page components |
| `app/routes/` | Page-level components |
| `components/ui/` | 17 shadcn/ui primitive components (Button, Input, Dialog, Select, etc.) — use these, never reinvent |
| `components/layout/` | App shell: `header.tsx` (top bar), `command-palette.tsx` |
| `components/dashboard/` | Drag-and-drop layout engine (`layout-engine.tsx`), pane containers, floating panels, drop targets, add-widget dialog |
| `components/widgets/` | Domain widgets: `screener-widget.tsx`, `chart-widget.tsx`, `watchlist-widget.tsx`, `community-feed-widget.tsx` |
| `components/screener/` | Screener sub-components: column editor, formula editor (Monaco), list dialogs, column properties |
| `hooks/` | Custom hooks for widget coordination, WebSocket subscriptions, screener logic |
| `queries/` | TanStack Query hooks for server state — lists, column sets, conditions, symbols |
| `stores/` | Zustand stores: `layout-store.ts` (layouts + theme), `auth-store.ts`, `screener-store.ts`, `ui-store.ts`, `widget-state-store.ts` |
| `lib/api.ts` | Axios instance + typed API helpers |
| `lib/ws.ts` | WebSocket client management |
| `lib/terminal-datafeed.ts` | TradingView charting library datafeed adapter |
| `lib/register-widgets.ts` | Widget registry — maps widget type strings to components |
| `types/` | Shared TypeScript types: `layout.ts`, `models.ts`, `api.ts`, `ws.ts` |

### Backend Module Map

| Module                  | Responsibility                                                                                                                                                               |
| ----------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `main.py`               | App entry point — mounts REST API at `/api/v1` and WebSocket at `/ws`. On startup: initializes `MarketDataManager` and `CandleManager`, preloads symbols.                    |
| `api.py`                | Aggregates all routers into a single `api_router`.                                                                                                                           |
| `config.py`             | Pydantic `Settings` loaded from `.env`. Required: `DATABASE_URL`, `OCI_BUCKET`, `OCI_CONFIG`, `OCI_KEY`.                                                                     |
| `dependencies.py`       | `lru_cache`-backed singletons for `MarketDataManager`, `CandleManager`, `TradingViewDataProvider`, and the OCI `fs`.                                                         |
| `market_feed/`          | `OHLCStore` (in-memory OHLCV DataFrame store), `TradingViewDataProvider` (fetches + caches data in OCI), `MarketDataManager` (coordinates loading + 5s polling + broadcast). |
| `realtime/`             | WebSocket handler + `RealtimeSession` — handles subscriptions to chart data, quotes, and screener updates.                                                                   |
| `formula/`              | Custom expression language with full lexer → parser → AST → evaluator pipeline. Powers screener conditions and column values.                                                |
| `scan/engine.py`        | Runs conditions and column formulas across all symbols using `MarketDataManager`.                                                                                            |
| `candles/`              | `UpstoxFeed` (WebSocket-based live feed), `UpstoxClient`, `CandleManager` (routes live candles to subscribers).                                                              |
| `lists/`                | User and system-defined stock lists (persisted in Postgres).                                                                                                                 |
| `column/`, `condition/` | Screener column set and condition CRUD APIs.                                                                                                                                 |
| `symbols/`              | Symbol search and management, backed by OCI-stored parquet files.                                                                                                            |
| `database/`             | SQLAlchemy engine + `Base`, Alembic migrations in `database/revisions/`.                                                                                                     |
| `auth/`                 | JWT-based auth — `/auth/register`, `/auth/login`, token verification.                                                                                                        |
| `storage/fs.py`         | OCI filesystem singleton via `ocifs`.                                                                                                                                        |
| `cli.py`                | Typer CLI for DB management and data refresh (see commands below).                                                                                                           |

## Commands

### Backend

```bash
# Run dev server (auto-reload)
uv run fastapi dev src/terminal/main.py

# Run all tests (uses testcontainers — requires Docker)
uv run pytest tests

# Run a single test file
uv run pytest tests/scan/test_scan_engine.py

# Run a single test
uv run pytest tests/scan/test_scan_engine.py::test_name

# Lint and auto-fix
ruff check --fix .

# Database migrations
uv run terminal database upgrade          # apply all migrations
uv run terminal database make-migrations -m "description"  # generate migration
uv run terminal database init             # initialize fresh DB

# Refresh market data (CLI)
uv run terminal symbol refresh
uv run terminal market-data refresh-daily
```

### Frontend (`src/web/`)

```bash
npm run dev      # Vite dev server
npm run build    # TypeScript check + production build
npm run lint     # ESLint
```

### Local Database

```bash
docker compose up -d   # starts postgres:15 on port 5432
```

## Key Patterns

**Dependency injection**: Singletons are created via `lru_cache` in `dependencies.py` and injected into FastAPI routes via `Depends(...)`. Tests override these with `api.dependency_overrides`.

**Model registration for Alembic**: All SQLAlchemy models must be imported in `src/terminal/__init__.py` to be visible to Alembic's autogenerate. Without this, `make-migrations` will produce an empty migration even though the model exists. When adding a new model, always add its import there:

```python
# src/terminal/__init__.py
from terminal.your_module.models import YourModel  # noqa: F401
```

**Testing**: The `conftest.py` session fixture uses `testcontainers` to spin up a real Postgres container. The `client` fixture wires in a test DB session and creates an `AsyncClient` against the FastAPI app directly (no network). Always use `pytest-asyncio` with `asyncio_mode = "strict"` — mark async tests with `@pytest.mark.asyncio`.

**Formula language**: Formulas (e.g., `close > SMA(close, 20)`) are parsed by `terminal/formula/` into an AST and evaluated against Pandas DataFrames. To add functions, extend `formula/functions.py`. Errors raise `FormulaError` from `formula/errors.py`.

**Real-time flow**: TradingView Scanner API is polled every 5s → `OHLCStore` updated → `BroadcastChannel` notifies all WebSocket sessions. Upstox WebSocket provides live Indian market candles.

**OCI storage**: Market data (parquet) is stored in OCI object storage and accessed via `ocifs`. Credentials (`OCI_CONFIG`, `OCI_KEY`) are base64-encoded in `.env`. The `abs_file_path` helper prefixes paths with `bucket/v2/`.

## Frontend Key Patterns

**Widget system**: Each widget is a React component registered in `lib/register-widgets.ts`. Widgets receive `instanceId`, `settings`, and `onSettingsChange` props. Settings are serialized JSON stored inside the layout. Widgets subscribe to a `channel` (string key) for cross-widget symbol sync — e.g., clicking a symbol in the screener updates the chart on the same channel.

**State split**: Use TanStack Query (`queries/`) for all server data (lists, column sets, symbols). Use Zustand (`stores/`) for client-only UI state (active layout, theme, maximized pane). Do not store server data in Zustand.

**TanStack Query config**: Stale time is `Infinity` — data is not automatically refetched on focus/reconnect. Manual `invalidateQueries` after mutations. Retry count: 1.

**Virtualized tables**: The screener uses TanStack Virtual with a fixed row height of `28px` and overscan of 15. All row-level components (`ScreenerRow`) are wrapped in `React.memo`. Sort state is applied before virtualizing.

**Real-time updates**: WebSocket messages from `/ws` drive screener and quote updates. The `useScreener` hook manages subscription + data merging. Cell changes trigger `.cell-flash-up` / `.cell-flash-down` CSS animations via class toggling.

**Layout persistence**: The active layout (pane tree + widget settings) is saved to the server via TanStack Query mutations whenever it changes. `layout-store.ts` is the source of truth for local layout state.

**Adding a new widget**:
1. Create `components/widgets/your-widget.tsx`
2. Register it in `lib/register-widgets.ts`
3. Define its settings type in `types/layout.ts`

**Styling rules**: Always use Tailwind utility classes with CSS token variables (`bg-background`, `text-foreground`, `border-border`). Never use hardcoded colors. See `docs/design-system.md` for full conventions.

## Test

- For backend codebase, always generate the test files in the `tests/` directory.
- For frontend codebse, don't need to generate test files. But ensure the code is working

## PLAN

- Ath the nd of each plan, give. amlist of unresolved question to answer if any. Makr the question extremely concise. Sacrifice grammar for conciseness.
- Whenever you are done with the plan and the work is approved, you should saved the plan in the `docs/<PLAN NAME>.md` file.
