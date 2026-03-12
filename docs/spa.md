# Big-Bang Migration: React SPA + Supabase + Local Engines

## Context

The stock market terminal currently runs as a FastAPI + React stack with a Python backend handling auth, CRUD, formula evaluation, screener sessions, real-time WebSocket, broker integrations, and market data management. The goal is to eliminate the Python server entirely, replacing it with:

- **Supabase** for auth (email/password) and Postgres with RLS
- **Browser Web Workers** for formula evaluation, screener engine, chart data, and alert evaluation
- **Cloudflare Worker** for proxying CORS/anti-bot-protected external APIs (TradingView scanner, StockTwits, charting library assets) AND serverless endpoints (broker OAuth, encrypted token management, notification dispatch)
- **IndexedDB** for client-side market data caching

This is a big-bang cutover with no dual-run period. Fresh Supabase start (no data migration). Full widget parity required.

---

## Phase 0: Foundation — Supabase + CF Worker + Auth (Week 1-2)

### 0A: Supabase Project + Schema

**Create**: `supabase/` directory at project root with Supabase CLI config

**Create**: `supabase/migrations/001_initial_schema.sql` — Full schema for all 14 tables:

| Table | Key Notes |
|-------|-----------|
| `lists` | `user_id uuid references auth.users(id)`, type enum (simple/color/combo/system), `symbols text[]`, `source_list_ids text[]` |
| `column_sets` | `columns jsonb` (array of ColumnDef objects) |
| `condition_sets` | `conditions jsonb`, `conditional_logic text`, `timeframe text`, `timeframe_value text` |
| `formulas` | `body text`, `params jsonb` |
| `alerts` | `trigger_condition jsonb`, `guard_conditions jsonb`, `frequency text`, `notification_channels jsonb`, `drawing_id text` |
| `alert_logs` | FK to alerts, `trigger_value float`, `read boolean` |
| `broker_credentials` | Split RLS: users SELECT own rows, service_role for INSERT/UPDATE/DELETE. `encrypted_token text` only accessed by CF Worker |
| `broker_defaults` | Unique constraint on `(user_id, capability, market)` |
| `user_preferences` | Unique on `user_id`, `layout jsonb`, `settings jsonb` |
| `user_charts` | `content jsonb` (TradingView chart state) |
| `user_study_templates` | Unique on `(user_id, name)`, `content jsonb` |
| `user_notification_channels` | `channel_type text`, `config jsonb`, `is_active boolean` |

All tables: `id text PK default gen_random_uuid()::text`, `user_id uuid references auth.users(id) on delete cascade`, `created_at/updated_at timestamptz` with auto-update trigger. RLS enabled on all tables with `auth.uid() = user_id` policy.

**Create**: `supabase/migrations/002_bootstrap_rpc.sql` — RPC function for default color lists on first login (replaces server-side `ensure_default_lists`).

> Note: No `supabase/functions/` directory needed — all serverless logic lives in the Cloudflare Worker (`packages/cf-worker/`).

### 0B: Supabase Auth in Frontend

**Create**: `src/web/src/lib/supabase.ts`
- `createClient<Database>(VITE_SUPABASE_URL, VITE_SUPABASE_ANON_KEY)`
- Typed with generated DB types

**Rewrite**: `src/web/src/stores/auth-store.ts`
- `login(email, password)` → `supabase.auth.signInWithPassword({ email, password })`
- `register(email, password)` → `supabase.auth.signUp({ email, password })`
- `logout()` → `supabase.auth.signOut()`
- `loadBoot(queryClient)` → `supabase.auth.getSession()` then parallel Supabase queries for lists, column_sets, condition_sets, formulas, preferences
- Remove `terminalWS.connect(token)` — replaced by worker initialization in Phase 5
- `onAuthStateChange` listener for session recovery

**Modify**: `src/web/src/app/routes/login.tsx` and `register.tsx`
- Change fields from username/password to email/password
- Update form submission to call new auth store methods

**Modify**: `src/web/src/types/api.ts`
- `LoginRequest` → `{ email: string; password: string }` (was username)
- Remove `TokenResponse` (Supabase handles tokens internally)

**Modify**: `src/web/src/types/models.ts`
- `User` → `{ id: string; email: string }` (was username)

### 0C: Cloudflare Worker Proxy

**Create**: `packages/cf-worker/` directory

**Create**: `packages/cf-worker/wrangler.toml`

**Create**: `packages/cf-worker/src/index.ts` — Router with endpoints:

| Endpoint | Purpose | Notes |
|----------|---------|-------|
| `POST /scanner/scan` | Proxy TradingView Scanner API | Adds origin/referer/UA headers, JSON pass-through |
| `GET /community/global/:feed` | Proxy StockTwits global feeds | Trending, bullish, bearish |
| `GET /community/:symbol/:feed` | Proxy StockTwits symbol feeds | Per-symbol feeds |
| `GET /tv/*` | Proxy TradingView charting library CDN | Static JS/CSS (replaces Vite proxy) |
| `GET /broker/:provider/auth-url` | Generate OAuth redirect URL | Provider API keys in CF secrets |
| `POST /broker/:provider/callback` | Exchange OAuth code for token | Encrypts token, stores in Supabase `broker_credentials` via service_role |
| `GET /broker/:provider/status` | Check broker token validity | Decrypts from KV/secrets, validates with Upstox API |
| `POST /broker/:provider/token` | Get short-lived token for browser | For chart worker Upstox WS. Requires Supabase JWT auth |
| `POST /notify` | Dispatch notifications | Telegram bot / web push. Called by browser alert engine |

**Create**: `packages/cf-worker/src/scanner.ts`, `community.ts`, `tv-proxy.ts`, `broker.ts`, `notify.ts`, `auth.ts` (verify Supabase JWT)

**Secrets** (via `wrangler secret put`): `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `UPSTOX_API_KEY`, `UPSTOX_API_SECRET`, `UPSTOX_REDIRECT_URI`, `ENCRYPTION_KEY`, `TELEGRAM_BOT_TOKEN`, `VAPID_*`

**KV namespace**: `BROKER_TOKENS` — encrypted token storage (alternative to Supabase Vault, since we're all-CF now)

**Verify**: Deploy CF Worker, confirm `/scanner/scan` returns valid TradingView data, `/community/*` returns StockTwits data, `/broker/upstox/auth-url` returns valid OAuth URL.

---

## Phase 1: TypeScript Formula Engine (Week 2-3)

Port the complete formula engine from Python (`src/terminal/formula/`) to TypeScript for execution in Web Workers. This is the most critical port — correctness must be validated against the Python implementation.

### Architecture

Replace `pd.DataFrame` + `np.ndarray` with a `ColumnStore` backed by `Float64Array`:

```
ColumnStore = { length: number; columns: Record<string, Float64Array> }
```

### Files to Create

All under `src/web/src/engine/formula/`:

| File | Ports From | Key Details |
|------|-----------|-------------|
| `column-store.ts` | New (replaces DataFrame) | `{ length, columns }` with factory from OHLCV typed arrays |
| `ast-nodes.ts` | `formula/ast_nodes.py` | `NumberLiteral`, `FieldRef`, `ShiftExpr`, `UnaryOp`, `BinOp`, `FuncCall` as discriminated union |
| `errors.ts` | `formula/errors.py` | `FormulaError` class with message, position, expected, hint |
| `lexer.ts` | `formula/lexer.py` | Same token types, identifiers uppercased, same position tracking |
| `parser.ts` | `formula/parser.py` | Same recursive descent grammar, same shorthand (SMAC126), same UDF expansion with `#param#value` |
| `fields.ts` | `formula/fields.py` | C/O/H/L/V/T + derived (HLC3, HL2, OHLC4), maps to ColumnStore keys |
| `functions.ts` | `formula/functions.py` | Registry pattern. SMA/EMA/MIN/MAX/HIGHEST/LOWEST/RMV — all on Float64Array |
| `evaluator.ts` | `formula/evaluator.py` | Tree-walking, vectorized ops on Float64Array. Arithmetic via loops (no NumPy ufuncs) |
| `params.ts` | `formula/params.py` | Extract `param NAME = VALUE` declarations from multi-line formulas |
| `index.ts` | `formula/__init__.py` | Public API: `parse()`, `evaluate()`, `preprocess()` |

### Function Implementations (replacing NumPy/pandas)

- **SMA**: Cumulative sum approach — O(n) with prefix sum, not nested loop
- **EMA**: Same algorithm as Python (seed with SMA of first `period` values, then `(source[i] - prev) * multiplier + prev`)
- **MIN/MAX/HIGHEST/LOWEST**: Deque-based sliding window for O(n)
- **RMV**: Direct port of the multi-rolling-window calculation using the above primitives
- **Shift**: Copy array with offset, fill head with NaN
- **Arithmetic**: Loop over Float64Array pairs (+ - * /), handle NaN via `isNaN()` checks
- **Comparison**: Same, returning `Uint8Array` (0/1) for boolean results
- **Boolean AND/OR/NOT**: Operate on Uint8Array, NaN-safe (NaN → false)

### Testing

**Create**: `src/web/src/engine/formula/__tests__/` with Vitest tests
- Port all fixtures from `tests/formula/` (if they exist) or create comprehensive test suite
- Test each function against known values (e.g., SMA of [1,2,3,4,5] with period 3)
- Test parser for every grammar production
- Test shorthand expansion (SMAC126 → SMA(C, 126))
- Test NaN propagation, division by zero
- Test `_to_bool` equivalent (NaN → false)

**Verify**: All formula unit tests pass. Cross-verify a few cases by running the same formula in Python and comparing results.

---

## Phase 2: Market Data Worker + IndexedDB Cache (Week 3-4)

Port `OHLCStore` + market data fetching to a Web Worker with IndexedDB persistence.

### Files to Create

All under `src/web/src/engine/market-data/`:

| File | Ports From | Key Details |
|------|-----------|-------------|
| `ohlc-store.ts` | `market_feed/store.py` | Ring buffer with `Float64Array` for timestamps and `Float32Array(capacity, 5)` for OHLCV. Keyed by `(symbol, timeframe)`. Same `load_history()`, `add_realtime()`, `get_data()` API |
| `idb-cache.ts` | New | IndexedDB wrapper. One object store per timeframe. Keys = symbol tickers, values = serialized ArrayBuffers. On boot: hydrate OHLCStore from IDB first (instant), then fetch fresh |
| `fetcher.ts` | `market_feed/provider.py` (partial) | Fetch from CF Worker `/scanner/scan`. Parse TradingView scanner response into OHLCV records. Replaces `PartitionedProvider` (no OCI, no parquet — CF Worker returns JSON) |
| `worker.ts` | New | Worker entry point. Initializes OHLCStore, IDB cache, fetcher. Handles messages: INIT, SUBSCRIBE, GET_OHLCV. Runs 5-second polling loop |
| `client.ts` | New | Main-thread Comlink wrapper exposing typed RPC methods |
| `types.ts` | New | Shared message types, OHLCV record types |
| `broadcast.ts` | `market_feed/manager.py` (BroadcastChannel) | Worker-internal pub/sub for candle updates (same debounce pattern as Python) |

### OHLCStore Port Details

The Python `OHLCStore` uses pre-allocated `np.zeros` arrays as ring buffers. The TS port is identical:
- `timestamps: BigInt64Array(capacity)` or `Float64Array(capacity)` for Unix seconds
- `ohlcv: Float32Array(capacity * 5)` — interleaved OHLCV, stride 5
- Same ring buffer logic: if `size >= capacity`, shift left by 1
- `getData()` returns a `ColumnStore` (not DataFrame) for use with formula engine

### Polling Loop

Replaces server-side `MarketDataManager._stream_loop()`:
1. Every 5 seconds: `POST /scanner/scan` to CF Worker with configured symbols
2. Parse response, call `store.addRealtime()` for each updated symbol
3. Post `UPDATE` messages to main thread for changed symbols
4. Persist updated data to IndexedDB periodically (every 30s or on visibility change)

### Symbol Data

Symbols (5000 items) are currently loaded from OCI parquet at boot. New approach:
- Fetch from source (CF Worker proxy or Supabase Storage) at boot
- Cache in IndexedDB for instant subsequent loads
- Manual "Refresh Symbols" button in UI to re-fetch
- Symbol search runs client-side (simple string matching on ticker/name)
- System lists (e.g., "All NSE", "Nifty 50") are computed dynamically at runtime by filtering the cached symbol data (no DB storage)

**Verify**: Worker starts, fetches data from CF Worker, stores in IndexedDB, OHLCStore returns correct ColumnStore data.

---

## Phase 3: Screener Worker (Week 4-5)

Port `ScreenerSession` from `src/terminal/realtime/screener.py` to a Web Worker.

### Files to Create

All under `src/web/src/engine/screener/`:

| File | Ports From |
|------|-----------|
| `worker.ts` | Worker entry point, manages multiple ScreenerSession instances |
| `session.ts` | `realtime/screener.py` (ScreenerSession) — core logic |
| `client.ts` | Main-thread typed API |
| `types.ts` | Message types matching current WS protocol |

### Session Logic Port

The `ScreenerSession` does:
1. Load list symbols (now from Supabase via main thread message)
2. Load column definitions (passed in `create_screener` params)
3. Pre-parse formula ASTs (using TS formula engine)
4. Evaluate conditions across symbols → filter to passing tickers
5. Evaluate column formulas for visible tickers → column values
6. Background loops: filter re-eval every N seconds, values update on market data changes (1s debounce)
7. Diff detection: only send changed columns

**Key difference from Python**: No DB access from worker. The worker receives symbols and metadata from the main thread (which fetches from Supabase). Market data comes from the market data worker (shared via `BroadcastChannel` or direct message passing between workers).

### Message Protocol (identical semantics to current WS)

```
Main → Worker: create_screener, modify_screener, destroy_screener
Worker → Main: screener_filter, screener_values, screener_errors
```

Same payload shapes as `src/terminal/realtime/models.py`: `ScreenerFilterRow { ticker, name, logo, v }`, `ScreenerValues { [colId]: values[] }`.

**Verify**: Screener worker receives create request, evaluates formulas, returns filtered rows + column values. Values update when market data changes.

---

## Phase 4: Chart Worker (Week 5)

### Files to Create

All under `src/web/src/engine/chart/`:

| File | Ports From |
|------|-----------|
| `worker.ts` | Worker entry, manages chart sessions |
| `session.ts` | `realtime/session.py` chart handling |
| `client.ts` | Main-thread API |

### Responsibilities

1. **Symbol resolution**: From bundled symbol list (no server call)
2. **Historical candles**: From market data worker (daily) or CF Worker proxy (intraday via TradingView)
3. **Live updates**: From market data worker polling (daily candles) or direct Upstox WebSocket connection (intraday) using token from CF Worker `POST /broker/upstox/token`
4. **Same message protocol**: `create_chart`, `get_bar`, `subscribe_bar`, `chart_series`, `chart_update`

**Modify**: `src/web/src/lib/terminal-datafeed.ts`
- Replace WS-based `ChartSession` calls with chart worker client calls
- Same `IDatafeedChartApi` interface, different transport

**Verify**: Chart widget loads historical data, displays candles, receives live updates.

---

## Phase 5: Internal Message Bus (Week 4-5, parallel with Phase 3)

Replace `TerminalWebSocket` (`src/web/src/lib/ws.ts`) with a local message bus routing between main thread and workers.

### Files to Create/Modify

**Create**: `src/web/src/engine/message-bus.ts`
- Same `{ m: string; p?: unknown[] }` message format as current WS
- Routes by message type prefix: `screener_*` → screener worker, `chart_*`/`resolve_*`/`*_bar` → chart worker, `quote_*` → market data worker
- Exposes `on(type, handler)` and `send(msg)` — identical API to current `TerminalWebSocket`
- No reconnect logic needed (workers don't disconnect)

**Modify**: `src/web/src/hooks/use-websocket.ts`
- Return `MessageBus` singleton instead of `TerminalWebSocket`
- Same hook interface: `{ send, on, isConnected }` (isConnected always true)

**Delete**: `src/web/src/lib/ws.ts`

**Key insight**: The `useScreener` hook at `src/web/src/hooks/use-screener.ts` uses `useWebSocket().send()` and `useWebSocket().on()` — by swapping the transport to MessageBus, the hook needs zero changes to its message handling logic.

**Verify**: Screener widget works end-to-end with workers instead of WS.

---

## Phase 6: Frontend Data Layer (Week 5-6)

Replace all Axios API calls with Supabase JS client.

### Files to Create

**Create**: `src/web/src/lib/repositories/` — One repository per domain:

| File | Replaces API endpoints |
|------|----------------------|
| `lists.ts` | `/lists/*` — `supabase.from('lists').select/insert/update/delete` |
| `column-sets.ts` | `/columns/*` |
| `condition-sets.ts` | `/conditions/*` |
| `formulas.ts` | `/formula/functions` |
| `charts.ts` | `/charts/*`, `/charts/study-templates` |
| `preferences.ts` | `/preferences` |
| `alerts.ts` | `/alerts/*`, `/alerts/logs` |
| `notifications.ts` | `/notifications/channels` |

### Files to Modify

**Modify**: All query hooks in `src/web/src/queries/`:
- `use-lists.ts` → use `listsRepo.getAll()` instead of `api.lists.list()`
- `use-column-sets.ts` → use `columnSetsRepo.getAll()`
- `use-condition-sets.ts` → use `conditionSetsRepo.getAll()`
- `use-formulas.ts` → use `formulasRepo.getAll()`
- `use-alerts.ts` → use `alertsRepo.getAll()`
- `use-layout.ts` → use `preferencesRepo.get()` / `preferencesRepo.upsert()`
- `use-community-feed.ts` → fetch from CF Worker URL instead of `/api/v1/community/`

**Boot sequence** in auth-store:
```typescript
const [lists, columnSets, conditionSets, formulas, preferences] = await Promise.all([
  supabase.from('lists').select('*'),
  supabase.from('column_sets').select('*'),
  supabase.from('condition_sets').select('*'),
  supabase.from('formulas').select('*'),
  supabase.from('user_preferences').select('*').maybeSingle(),
]);
// Hydrate TanStack Query caches (same as current boot flow)
```

**Formula validation**: Currently `POST /formula/validate` runs on the backend. Now runs entirely client-side using the TS formula engine — parse + evaluate against sample data. The `EditorConfig` for Monaco is generated statically from the registered function list.

**Delete**: `src/web/src/lib/api.ts`

**Verify**: All CRUD operations work via Supabase. Lists, columns, conditions, formulas create/read/update/delete correctly with RLS.

---

## Phase 7: Broker + Notifications via CF Worker (Week 6-7)

Broker and notification endpoints are part of the same Cloudflare Worker deployed in Phase 0C. This phase implements the actual logic.

### Files to Create/Complete in CF Worker

All under `packages/cf-worker/src/`:

| File | Purpose | Key Details |
|------|---------|-------------|
| `broker.ts` | All broker endpoints | Auth URL generation, OAuth code exchange, token validation, short-lived token retrieval |
| `notify.ts` | Notification dispatch | Telegram bot API, web push (VAPID) |
| `auth.ts` | JWT verification middleware | Verifies Supabase JWT from `Authorization` header, extracts `user_id` |
| `crypto.ts` | Token encryption/decryption | Encrypt broker tokens before storing in `broker_credentials` table |

**Token storage**: Encrypted tokens stored in `broker_credentials.encrypted_token` column. CF Worker uses `SUPABASE_SERVICE_ROLE_KEY` to read/write this table. Encryption key stored as CF Worker secret (`ENCRYPTION_KEY`). Uses Web Crypto API (AES-GCM) for encrypt/decrypt — no external Fernet dependency.

### Frontend Changes

**Modify**: `src/web/src/hooks/use-brokers.ts`
- Replace REST calls with `fetch(CF_WORKER_URL + '/broker/upstox/*')` with Supabase JWT in Authorization header
- Replace WS `broker_status` listener with polling or Supabase Realtime subscription on `broker_credentials` table
- OAuth popup flow: open auth-url result, popup redirects to CF Worker callback, main window polls status
- **Upstox only** — remove Kite adapter references

**Modify**: Broker widget — same UI, different data source, Upstox only

**Verify**: Upstox OAuth flow works end-to-end. Connect Upstox, see credentials stored, chart worker can connect to Upstox WS with retrieved token.

---

## Phase 8: Alert Engine in Browser (Week 6-7, parallel with Phase 7)

### Files to Create

Under `src/web/src/engine/alerts/`:

| File | Purpose |
|------|---------|
| `engine.ts` | Alert evaluation loop — runs in market data worker |
| `types.ts` | Alert types, trigger results |

### Logic

- Subscribes to market data updates from OHLCStore
- Pre-parses formula ASTs for all active alerts
- On each update cycle: evaluate trigger condition + guard conditions
- On trigger: insert `alert_log` to Supabase, call CF Worker `/notify` endpoint, post `alert_triggered` to main thread
- Frequency enforcement: once, once_per_minute, once_per_bar, end_of_day
- Only evaluates while app is open (per requirements)

**Modify**: `src/web/src/hooks/use-alerts.ts` (if exists) — listen to message bus for `alert_triggered` instead of WS

**Verify**: Create alert, wait for condition to be met, see trigger in alert logs.

---

## Phase 9: Widget Integration + Parity (Week 7)

Update each widget to use new data layer. Most widgets need minimal changes since we preserved message semantics.

| Widget | Changes Needed |
|--------|---------------|
| **Screener** | None if useScreener/useWebSocket swap worked in Phase 5 |
| **Chart** | TerminalDatafeed already updated in Phase 4 |
| **Community Feed** | Change fetch URL from `/api/v1/community/` to CF Worker URL |
| **Community Global** | Same as above |
| **Broker** | Already updated in Phase 7 |
| **Alerts** | Already updated in Phase 8 |
| **Bubble Chart** | Uses screener data — should work if screener works |
| **Mini Chart** | Uses chart data — should work if chart worker works |

**Modify**: `src/web/src/app/providers.tsx`
- Remove WS initialization from auth flow
- Add worker initialization (create market data, screener, chart workers)
- Initialize message bus

**Modify**: `src/web/src/stores/layout-store.ts`
- Layout save: `supabase.from('user_preferences').upsert()` instead of preferences API

**Modify**: `src/web/vite.config.ts`
- Remove API proxy (`/api/v1` → `localhost:8000`)
- Remove WS proxy (`/ws` → `localhost:8000`)
- Add CF Worker URL as env var for dev
- Configure worker build (Vite handles Web Workers natively with `?worker` imports)

---

## Phase 10: Cleanup + Cutover (Week 8)

### Files to Delete

**Entire backend**:
- `src/terminal/` (all Python source)
- `tests/` (Python test suite)
- `pyproject.toml`, `uv.lock`

**Frontend cleanup**:
- `src/web/src/lib/api.ts` (replaced by repositories)
- `src/web/src/lib/ws.ts` (replaced by message-bus)

**Infrastructure**:
- `docker-compose.yaml` (no local Postgres needed — Supabase handles DB)
- `Dockerfile` (or rewrite for static SPA hosting)

### New Dependencies

**Add to `src/web/package.json`**:
- `@supabase/supabase-js` — Supabase client
- `comlink` — Worker RPC (optional, can use raw postMessage)
- `idb-keyval` or `idb` — IndexedDB wrapper

### Build & Deploy Changes

- SPA deployed to Vercel/Cloudflare Pages/Supabase Hosting (static files only)
- CF Worker deployed via `wrangler deploy` (includes proxy + broker + notifications)
- No Python runtime needed anywhere

---

## Testing Strategy

### Unit Tests (Vitest)
- Formula engine: lexer, parser, evaluator, each function — comprehensive parity with Python
- OHLCStore: ring buffer behavior, load/update/get
- Screener evaluator: condition filtering, column computation

### Integration Tests
- Supabase RLS: sign in as User A, verify cannot read User B's data
- CF Worker broker endpoints: mock Upstox APIs, test OAuth exchange and token encryption
- Worker communication: send messages, verify responses

### E2E Verification (Manual)
- Email signup → login → boot data loads
- Screener: select list, apply columns, see filtered results, verify live updates
- Chart: select symbol, see candles, verify live updates
- Alerts: create, trigger, see notification
- Broker: OAuth flow, account display
- Layout: save, reload page, verify persistence
- Community feed: trending/symbol feeds display

### Acceptance Gates
- Zero network calls to `/api/v1` or `/ws`
- `npm run build` succeeds with no Python dependencies
- All 8 widgets render and function
- Python server process is not running

---

## Decisions (Resolved)

1. **Symbol data**: Load from source at boot, cache locally in IndexedDB/localStorage. Manual refresh button in UI to re-fetch. No build-time bundling.

2. **System lists**: Computed dynamically at runtime on the client side from the cached symbol data (e.g., "All NSE" = filter symbols where exchange === "NSE"). Not stored in Supabase.

3. **Broker feeds**: Browser connects directly to Upstox WebSocket (no CORS issues). **Kite support removed** for the initial migration — only Upstox.

4. **TradingView charting library assets**: Proxied through Cloudflare Worker.

5. **Broker token encryption**: Use **AES-GCM via Web Crypto API** in Cloudflare Worker. Encryption key stored as CF Worker secret. No Fernet or Supabase Vault dependency.

6. **Worker architecture**: **Dedicated workers** — separate Worker for market data, screener, and chart. Each has its own lifecycle. Workers communicate via `postMessage` when needed (e.g., screener worker requests data from market data worker via main thread relay).
