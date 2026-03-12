# Chrome Extension Conversion Plan

## Context

Convert the entire stock market terminal (React frontend + Python FastAPI backend) into a Chrome Extension (Manifest V3). Use **Supabase** for auth, database, and storage. Use **Cloudflare Workers** as proxy for TradingView Scanner API (symbol lists) and TradingView Streamer WebSocket (historical bars + live quotes — CORS/origin restricted). Formula engine ported to TypeScript with TypedArrays. Candle data (1500 bars/symbol, per exchange/market) cached in **OPFS** and loaded into TypedArrays for processing.

---

## Architecture Overview

```
extension/                           # In project root, move to root when migration complete
├── manifest.json
├── vite.config.ts                   # CRXJS Vite plugin
├── src/
│   ├── service-worker/
│   │   ├── index.ts                 # Entry, alarm registration, port mgmt
│   │   ├── message-handler.ts       # chrome.runtime.onMessage dispatcher
│   │   ├── alarm-handler.ts         # chrome.alarms: candle download + screener symbol refresh
│   │   ├── offscreen-manager.ts     # Offscreen doc (realtime sessions only)
│   │   ├── scan-engine.ts           # Runs conditions/columns against OHLCStore
│   │   └── alert-engine.ts          # Evaluates alerts (runs while panel open via port keepalive)
│   ├── offscreen/                   # Reserved for future background WS if needed
│   │   ├── offscreen.html
│   │   └── index.ts
│   ├── ui/                          # React UI (Side Panel + Full Page)
│   │   ├── side-panel.html          # Side panel entry
│   │   ├── full-page.html           # Full tab page (chrome-extension://id/full-page.html)
│   │   ├── main.tsx                 # Shared React entry (detects context)
│   │   ├── app/
│   │   │   ├── providers.tsx        # Supabase + React Query + Theme
│   │   │   └── routes.tsx           # Tab-based navigation
│   │   ├── app/routes/              # screener, chart, alerts, watchlist, community, broker, settings
│   │   ├── components/ui/           # shadcn/ui (from web)
│   │   ├── components/layout/
│   │   │   ├── app-shell.tsx        # Responsive: bottom-nav (panel) or sidebar (full page)
│   │   │   ├── bottom-nav.tsx
│   │   │   ├── sidebar-nav.tsx
│   │   │   └── header-bar.tsx
│   │   ├── components/screener/
│   │   ├── components/chart/        # Lightweight Charts + Upstox WS (direct, no CORS)
│   │   ├── components/alerts/
│   │   ├── components/watchlist/
│   │   ├── components/community/
│   │   ├── components/broker/
│   │   ├── hooks/
│   │   │   ├── use-extension-message.ts
│   │   │   ├── use-screener.ts
│   │   │   ├── use-chart-data.ts
│   │   │   ├── use-quote.ts
│   │   │   ├── use-alerts.ts
│   │   │   └── use-context-mode.ts  # Side panel vs full page
│   │   ├── stores/
│   │   ├── lib/
│   │   │   ├── supabase.ts          # All CRUD + auth (direct, no SW)
│   │   │   ├── message-protocol.ts
│   │   │   └── chart-datafeed.ts
│   │   ├── queries/                 # TanStack Query (backed by Supabase)
│   │   ├── types/
│   │   └── styles/globals.css
│   ├── formula/                     # TypeScript formula engine
│   │   ├── lexer.ts
│   │   ├── parser.ts
│   │   ├── ast-nodes.ts
│   │   ├── evaluator.ts             # Float64Array-based
│   │   ├── functions.ts             # 40+ indicators
│   │   ├── fields.ts
│   │   ├── params.ts
│   │   └── errors.ts
│   ├── data/
│   │   ├── ohlc-store.ts            # In-memory TypedArray ring buffers (1500 bars/symbol)
│   │   ├── candle-cache.ts          # OPFS persistence for candle data
│   │   └── symbol-store.ts
│   ├── market-data/
│   │   ├── scanner-client.ts        # CF Worker → TradingView Scanner (symbol lists only)
│   │   ├── streamer-client.ts       # CF Worker → TradingView Streamer WS (historical bars + quotes)
│   │   ├── upstox-client.ts         # Direct REST (chart sessions only, host_permissions)
│   │   └── data-manager.ts          # Coordinates sources, per-exchange/market loading
│   └── shared/
│       ├── constants.ts
│       └── utils.ts
├── supabase/
│   ├── config.toml
│   ├── migrations/
│   │   └── 001_initial_schema.sql   # Full schema + RLS
│   └── seed.sql
├── cloudflare-worker/
│   ├── src/
│   │   ├── index.ts                 # Router (plain Worker for REST, DO for WS)
│   │   ├── scanner-proxy.ts         # TradingView Scanner API proxy (symbol lists + metadata)
│   │   ├── streamer-do.ts           # Durable Object: TradingView Streamer WS proxy (persistent)
│   │   └── oauth-callback.ts        # Broker OAuth HTTPS redirect handler
│   ├── wrangler.toml
│   └── package.json
└── tests/
    ├── formula/
    ├── data/
    └── market-data/
```

---

## Data Flow: How OHLCV Data Actually Works

Understanding from the current backend:

### What each API provides:
- **TradingView Scanner API** (REST): Symbol lists with metadata + latest daily bar snapshot. Used for **screener symbol discovery** only.
- **TradingView Streamer** (WebSocket): **The actual source of historical OHLCV bars** (1500 bars/symbol). Also provides live quote updates (open, high, low, last_price, volume) for real-time data.
- **Upstox REST API**: Historical + intraday candles for Indian markets. Used **only during chart sessions**, not for bulk download.

### Data download flow (Extension):
```
chrome.alarms wakes SW (market-relevant schedule)
    ↓
SW connects to CF Worker WebSocket proxy (streamer-proxy)
    ↓
CF Worker connects upstream to wss://data.tradingview.com/socket.io/websocket
    ↓
Creates chart session, resolves symbols, streams 1500 bars per symbol
    ↓
SW receives bars, writes to OPFS (per-exchange binary files)
    ↓
SW loads into OHLCStore (Float64Array ring buffers, 1500 bars capacity)
    ↓
Formula engine evaluates against TypedArray views
```

### Screener symbol download flow:
```
chrome.alarms wakes SW
    ↓
SW calls CF Worker → TradingView Scanner API
    ↓
Gets symbol list + metadata for exchange/market
    ↓
Stores symbol metadata in Supabase or OPFS
```

### Real-time quote updates (while panel open):
```
UI opens → establishes chrome.runtime.connect() port → keeps SW alive
    ↓
SW connects to CF Worker streamer proxy (WebSocket)
    ↓
Subscribes to quote updates for active symbols
    ↓
Receives: open_price, high_price, low_price, last_price, volume, timestamp
    ↓
Builds intraday candle updates → updates OHLCStore in-place
    ↓
Re-evaluates formulas on dirty symbols
    ↓
Broadcasts SCREENER_VALUES to UI via port
```

### Chart session (Upstox candles for Indian market):
```
User opens chart for Indian symbol (e.g., NSE:RELIANCE)
    ↓
UI directly connects to Upstox (no CORS issues, no background needed)
    ↓
Upstox WebSocket (protobuf, pre-compiled static decoder) for live candle data
    ↓
Upstox REST for historical intraday candles (1m, 5m, etc.)
    ↓
Rendered directly in Lightweight Charts (all in UI context)
```

---

## Key Architecture Decisions

### 1. Supabase replaces the Python backend

**Supabase provides**: PostgreSQL (same schema), Auth, RLS, Realtime, Storage

**No API router in SW** — UI calls Supabase JS SDK directly for all CRUD.

**SW handles only**: Market data operations, formula/scan engine, alert evaluation, offscreen management.

### 2. OPFS for Candle Data Storage

**Why OPFS over IndexedDB**: Binary candle data (ArrayBuffers) benefits from OPFS's file-system-like API with better write performance and no serialization overhead. OPFS allows `FileSystemSyncAccessHandle` for high-throughput reads from the service worker.

**Storage layout**:
```
opfs-root/
├── candles/
│   ├── 1D/
│   │   ├── NSE.bin         # All NSE symbols, 1500 bars each
│   │   ├── BSE.bin
│   │   ├── NASDAQ.bin
│   │   └── ...
│   └── metadata.json       # ETags, last-downloaded timestamps per exchange
└── symbols/
    ├── NSE.json             # Symbol list + metadata
    └── ...
```

**Binary format per exchange file**:
- Header: `[num_symbols: u32, bars_per_symbol: u32]`
- Per symbol: `[ticker_len: u16, ticker: utf8, timestamps: Int32Array(1500), ohlcv: Float64Array(7500)]`
- Loaded directly into OHLCStore TypedArray views (zero-copy where possible)

### 3. Dual UI: Side Panel + Full Page

Same React codebase, two HTML entries:
- Side panel: bottom tab nav, compact
- Full page: sidebar nav, wider (closer to original layout engine)
- `use-context-mode()` hook detects mode
- "Open in full page" button in side panel header

### 4. TradingView Streamer: CF Worker Durable Object WebSocket Proxy

The streamer (`wss://data.tradingview.com/socket.io/websocket`) has CORS/origin restrictions. Implemented as a **Cloudflare Durable Object** for persistent WebSocket connections:

- **Durable Object** maintains the upstream TradingView WebSocket connection
- Survives idle periods (no 30s timeout like plain Workers)
- Accepts WebSocket from extension, relays bidirectionally to TradingView
- Sets correct `origin: https://in.tradingview.com`
- Handles TradingView's custom framing (`~m~N~m~{json}`)
- One DO instance per user session (or shared per exchange for efficiency)

Used for: **Historical bar downloads** (1500 bars/symbol, long-lived sessions) AND **live quote streaming**.

### 5. Broker OAuth via CF Worker HTTPS Redirect

Normal OAuth flow (no `chrome.identity`):
- Extension opens broker login URL in new tab
- Redirect URL: `https://your-worker.workers.dev/oauth/callback/:provider`
- CF Worker receives auth code, renders page that communicates back to extension
- Extension exchanges code for token, stores in Supabase (encrypted)

### 6. chrome.alarms — Limited Scope

Only two types of scheduled work:
| Alarm | Purpose |
|---|---|
| `candle-download:{exchange}:{timeframe}` | Download 1500 bars from TradingView Streamer, persist to OPFS |
| `symbol-refresh:{exchange}` | Refresh symbol lists from Scanner API |

**Alert evaluation** and **screener updates** do NOT use alarms. They run while the panel is open, kept alive by the chrome.runtime port connection.

### 7. Chart Sessions Run in UI (Not Background)

Upstox has no CORS issues. Chart sessions (Upstox WebSocket for live candles, Upstox REST for historical) run **directly in the UI** (side panel / full page). No offscreen document needed for charting. The UI connects to Upstox directly using the protobuf decoder (pre-compiled static).

Offscreen document is reserved only if future background WebSocket needs arise.

### 8. CORS Strategy

| Service | Method | Proxy? |
|---|---|---|
| Supabase | JS SDK (direct) | No |
| TradingView Scanner | CF Worker REST proxy | Yes (anti-bot + CORS) |
| TradingView Streamer | CF Worker WebSocket proxy | Yes (origin restriction) |
| Upstox REST | Direct from UI (no CORS) | No (chart sessions in UI) |
| Upstox WebSocket | Direct from UI (no CORS) | No (chart sessions in UI, protobuf static decoder) |
| Kite API | Direct from SW (host_permissions) | No |

### 9. Auth: Supabase Auth

- `supabase.auth.signUp()` / `signInWithPassword()` / `onAuthStateChange()`
- RLS policies on all tables (in migrations)
- No custom JWT

### 10. Formula Engine: TypeScript + TypedArrays

1:1 port from Python. Float64Array replaces NumPy. 1500-bar capacity.

---

## Database Schema (Supabase)

All tables with RLS policies in `supabase/migrations/001_initial_schema.sql`:

**Tables**: `lists`, `column_sets`, `condition_sets`, `formulas`, `alerts`, `alert_logs`, `broker_credentials`, `broker_defaults`, `user_charts`, `user_study_templates`, `user_preferences`, `user_notification_channels`

All have `user_id references auth.users(id)`, RLS enabled, policy: `auth.uid() = user_id`.

---

## Communication Architecture

```
┌──────────────────────────────┐
│  UI (Side Panel / Full Page) │
│  React + Supabase JS SDK     │──── CRUD/Auth ────► Supabase (direct)
│  TanStack Query              │
└──────────┬───────────────────┘
           │ chrome.runtime port (keepalive while panel open)
           │ + chrome.runtime.sendMessage (request/response)
           ▼
┌──────────────────────────────┐
│  Service Worker              │
│  ├─ alarm-handler            │──── chrome.alarms (candle download, symbol refresh)
│  ├─ data-manager             │──── CF Worker (scanner proxy, streamer WS proxy)
│  ├─ ohlc-store (memory)      │──── OPFS (candle cache, binary format)
│  ├─ streamer-client          │──── CF Worker WS proxy (live quotes while panel open)
│  ├─ scan-engine              │     (runs while panel open via port keepalive)
│  ├─ alert-engine             │     (runs while panel open via port keepalive)
│  └─ offscreen-manager        │
└──────────────────────────────┘

UI also directly connects to:
  ├─ Upstox REST (historical candles, no CORS)
  └─ Upstox WebSocket (live candles, protobuf static decoder, no CORS)
  (Chart sessions run entirely in UI context)
```

**Port keepalive model**: When the side panel or full page is open, it opens a `chrome.runtime.connect()` port. This keeps the SW alive for:
- Live quote streaming (via CF Worker streamer proxy)
- Scan engine evaluation (continuous while panel open)
- Alert evaluation (continuous while panel open)
- Screener updates broadcast to UI

When panel closes → port disconnects → SW stops live work (but alarms still fire for scheduled downloads).

---

## Implementation Phases

### Phase 1: Foundation + Supabase (~30 files, Weeks 1-3)
- Extension skeleton (manifest, CRXJS Vite, Tailwind, dual HTML entries)
- Supabase project (migrations with RLS, auth config)
- Supabase client in UI (`lib/supabase.ts`)
- Auth flow (sign up, sign in, session)
- App shell (responsive: bottom-nav / sidebar)
- Formula engine (full TS port: lexer, parser, AST, evaluator, 40+ functions)
- OHLCStore (TypedArray ring buffers, 1500 bars)
- OPFS candle cache (binary read/write)
- Service worker skeleton + alarm registration
- CF Worker (scanner proxy + streamer WS proxy + OAuth callback)
- **Deliverable**: Extension installs, both UI modes work, auth works, formula engine passes tests

### Phase 2: Screener + Data Pipeline (~25 files, Weeks 4-6)
- TanStack Query hooks → Supabase (lists, columns, conditions, formulas)
- Candle download alarm → CF Worker streamer → OPFS → OHLCStore
- Scanner API alarm → symbol lists per exchange
- Live quote streaming (while panel open via port)
- Screener table (virtualized, responsive)
- Scan engine (conditions + columns against OHLCStore)
- Chrome messaging: screener updates → UI
- shadcn/ui components
- **Deliverable**: Working screener with real data, formula filtering, real-time updates

### Phase 3: Charts + Watchlist (~12 files, Weeks 7-8)
- Lightweight Charts integration
- Chart datafeed (reads from OHLCStore + live quote stream)
- Watchlist view with mini charts
- Symbol search
- **Deliverable**: Candlestick charts, real-time price updates, watchlist

### Phase 4: Alerts + Notifications (~10 files, Weeks 9-10)
- Alert CRUD via Supabase
- Alert engine in SW (runs while panel open)
- chrome.notifications for triggers
- Alert logs to Supabase
- **Deliverable**: Formula alerts, notifications, persistent logs

### Phase 5: Broker Integration (~12 files, Weeks 11-12)
- OAuth via CF Worker HTTPS redirect (Upstox, Kite)
- Broker credentials encrypted in Supabase
- Upstox WebSocket in UI (protobuf static decoder, no CORS, direct connection)
- Upstox REST in UI for historical/intraday chart candles
- **Deliverable**: Broker OAuth, live Indian market charting (all in UI)

### Phase 6: Community + Polish (~8 files, Weeks 13-14)
- Community feed
- Preferences sync via Supabase Realtime
- Onboarding, edge cases, polish
- **Deliverable**: Full feature parity

**Total: ~97 new files**

---

## Critical Risks & Mitigations

| Risk | Severity | Mitigation |
|---|---|---|
| SW lifecycle | HIGH | Port keepalive (panel open = SW alive); alarms for scheduled downloads; OPFS for state recovery |
| Memory (1500 bars * 1000 symbols = 72MB) | MEDIUM | Lazy-load per exchange; LRU eviction; only active list in memory |
| CF Worker WS proxy reliability | MEDIUM | Durable Objects for persistent WS; auto-reconnect; one DO per session |
| OPFS access from SW | LOW | Use `navigator.storage.getDirectory()` (available in SW context since Chrome 102) |
| Formula engine correctness | MEDIUM | Port Python tests to Vitest; cross-validate |
| Broker OAuth redirect | SOLVED | CF Worker HTTPS callback; normal OAuth flow |
| TradingView Streamer CORS | SOLVED | CF Worker WebSocket proxy with correct origin |

---

## Critical Files to Port/Reference

| Source | Target | What |
|---|---|---|
| `src/terminal/formula/evaluator.py` | `src/formula/evaluator.ts` | Core evaluation |
| `src/terminal/formula/functions.py` | `src/formula/functions.ts` | 40+ indicators |
| `src/terminal/formula/lexer.py` | `src/formula/lexer.ts` | Tokenizer |
| `src/terminal/formula/parser.py` | `src/formula/parser.ts` | Parser |
| `src/terminal/market_feed/store.py` | `src/data/ohlc-store.ts` | Ring buffer (1500 bars) |
| `src/terminal/market_feed/manager.py` | `src/market-data/data-manager.ts` | Data coordinator |
| `src/terminal/scan/engine.py` | `src/service-worker/scan-engine.ts` | Scan engine |
| `src/terminal/tradingview/scanner.py` | `cloudflare-worker/src/scanner-proxy.ts` | Scanner proxy |
| `src/terminal/tradingview/streamer2.py` | `cloudflare-worker/src/streamer-proxy.ts` | Streamer protocol → CF Worker |
| `src/terminal/market_feed/tradingview.py` | `src/market-data/streamer-client.ts` | Bar download logic |
| `src/web/src/hooks/use-screener.ts` | `src/ui/hooks/use-screener.ts` | Screener hook |
| `src/web/src/styles/globals.css` | `src/ui/styles/globals.css` | Design tokens |
| `src/web/src/components/ui/*` | `src/ui/components/ui/*` | shadcn/ui |
| All SQLAlchemy models | `supabase/migrations/001_initial_schema.sql` | Schema + RLS |

---

## Verification Plan

1. **Supabase**: `supabase db reset` — migrations + RLS work
2. **Auth**: Sign up, sign in, session persistence across extension restarts
3. **Formula engine**: Port Python tests to Vitest, cross-validate
4. **OPFS**: Write candle data, read back, verify binary integrity
5. **OHLCStore**: Ring buffer with 1500 bars, TypedArray slicing
6. **Candle download**: Alarm triggers → CF Worker streamer → OPFS → OHLCStore
7. **Screener E2E**: Install extension, open side panel, verify live screener data
8. **Full page**: `chrome-extension://id/full-page.html` with wider layout
9. **Streamer proxy**: CF Worker relays TradingView WebSocket messages correctly
10. **Alerts**: Create → evaluate → notification → Supabase log
11. **Broker OAuth**: Upstox OAuth via CF Worker callback
12. **Build**: `npm run build` → valid extension, loads in `chrome://extensions`

---

## Resolved Decisions

1. **Supabase project**: Same project. Web app will be retired. Code lives in `extension/` folder at project root; once migration is complete, move to root.
2. **Symbol bootstrapping**: TradingView search API directly. Symbol search is implemented locally.
3. **Scan engine**: Runs locally (client-side in SW). No Supabase Edge Functions.
4. **CF Worker streamer proxy**: Durable Objects for persistent WS connections.
5. **Protobuf for Upstox WS**: Pre-compiled static decoder (small, fast).
6. **Study overlays**: Implement as-is (SMA/BB via Lightweight Charts `addLineSeries`).
7. **Chart sessions**: Run directly in UI (Upstox has no CORS). No background/offscreen needed.
8. **Build system**: CRXJS Vite plugin.
