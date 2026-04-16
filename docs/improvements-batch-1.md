# Improvements — Batch 1

Consolidated plan for 12 improvement items spanning lists, alerts, chart, screener, symbols, and chart-layout persistence.

## Scope

### Original 6
1. **Combo list auto-refresh on member change (frontend-only).** Backend already aggregates at read time; frontend must invalidate combo list queries whenever a member list mutates.
2. **Copy tickers as `EXCH:SYM,EXCH:SYM,…`** from a sidebar context-menu action.
3. **Delete list** — `DELETE /lists/{id}` endpoint; no cascade. Combo lists with dangling member IDs stay valid (existing query already skips missing rows). UI hides delete for color lists and `sys:*` lists.
4. **Browser system notifications for alerts** (via `Notification` API) in addition to the existing Sonner toast. Persistent notification center (bell icon + dropdown), last 50 entries persisted to `localStorage`. Permission requested via an explicit "Enable notifications" button in the center — no prompt on first trigger.
5. **Chart "Reload" action** in the chart widget header: cancels current datafeed subscription, clears cached bars, and re-runs the datafeed init (resolve → getBars → subscribeBars). Same path auto-fires on WS reconnect.
6. **15-minute interval diagnosis** — trace the resolution mapping path across `terminal-datafeed.ts`, `candles/models.py`, and `candles/upstox.py`; fix whatever is preventing 15m bars from loading.

### Extras 6
- **E1. Persist screener column sort** into widget settings so it round-trips through the layout store.
- **E2. Column groups** — reuse the existing `ColumnSet` backend + frontend queries. Gap is UX: ensure load/apply from the column editor is discoverable and functional.
- **E3. Daily symbols refresh** — add a background loop in `MarketDataManager` that reruns `symbols.service.refresh()` every 24 hours from boot.
- **E4. Symbol-search logo URL** — `/symbols/search` returns bare filenames in `logo`; `resolveSymbol` returns full URLs. Fix search to prefix the CDN/bucket URL like `resolveSymbol` does.
- **E5. Chart autosave** — a custom save-load adapter is already wired. Configure the TradingView chart widget options to enable `auto_save_delay` / appropriate save triggers so the adapter's save hooks fire automatically.
- **E6. Remove Zerodha login-on-load** — find the startup effect that requests Zerodha auth and remove it.

## Assumptions

- Combo refresh is a pure client-side query-invalidation change — no backend work.
- Delete list has **no cascade**. Combo lists are read-time views; orphan IDs are harmless.
- Browser notifications only fire when the document is hidden, to avoid doubling up with the in-view toast.
- E3 runs every 24h from boot. No cron needed; uses the existing `_data_refresh_loop` pattern.
- E5 TradingView autosave — reuse whatever adapter's `saveChart`/`saveLineToolsAndGroups` methods already call. No new save endpoint.

## Execution order

**Batch 1 — quick wins**
1. Remove Zerodha login on load (E6)
2. `DELETE /lists/{id}` endpoint + UI (#3)
3. Combo auto-refresh via query invalidation (#1)
4. Copy tickers action (#2)

**Batch 2 — alerts & chart**
5. Browser notifications + notification center (#4)
6. Chart reload button + reconnect hook (#5)

**Batch 3 — persistence & refresh**
7. Persist screener sort (E1)
8. Daily symbols refresh loop (E3)
9. Enable TradingView autosave (E5)

**Batch 4 — diagnose & integrate**
10. Fix symbol-search logo URL (E4)
11. Diagnose 15m interval (#6)
12. Verify column-set load/apply UX (E2)

## Implementation Notes

### #1 — Combo list auto-refresh
Invalidated `QUERY_KEYS.lists` in `useUpdateListMutation` and `useDeleteListMutation` so combo lists refetch when member lists change.

### #2 — Copy tickers
Added "Copy tickers" context-menu item in the list sidebar. Formats tickers as `EXCH:SYM,EXCH:SYM,...` and writes to clipboard via `navigator.clipboard.writeText`.

### #3 — Delete list
Added `DELETE /lists/{id}` FastAPI endpoint (no cascade). UI shows a "Delete list" option in the sidebar context-menu, hidden for color lists and `sys:*` lists.

### #4 — Browser notifications + notification center
Added `useNotificationsStore` (Zustand, localStorage-persisted, 50-entry cap). `NotificationBell` renders a bell icon + unread badge + dropdown. Fires `Notification` API only when `document.hidden`. Permission is opt-in via "Enable browser notifications" button in the dropdown.

### #5 — Chart reload button
Added a reload button to the chart widget header. Calls `tvWidget.activeChart().resetData()` to re-invoke `getBars`. The WS reconnect handler calls the same path.

### #6 — 15m interval fix
Root cause: `_do_get_candles` in `upstox.py` enforced a 30-day minimum window for all intraday intervals. With `chunk_days=7` for minutes, that caused 5 parallel Upstox calls. Under rate-limit backoff, total time exceeded the 15s frontend timeout.
- Reduced minimum intraday window from 30 days → `upstox_chunk_days(unit)` (7 days for minutes/hours), so each `getBars` = 1 Upstox call.
- Increased frontend `getBars` timeout in `chart-session.ts` from 15s → 30s as a safety net.

### E1 — Persist screener column sort
Added `sortColumn`/`sortDirection` to screener widget settings. `useScreener` reads initial sort from settings and calls `onSettingsChange` whenever sort changes.

### E2 — Column-set save/load UX
`column-editor.tsx` was missing the Save/Load UI entirely. Added "Load Set" dropdown (lists all saved sets, disabled when empty) and "Save Set" button that opens `SaveColumnSetDialog`. Wired `useColumnSetsQuery`, `useCreateColumnSetMutation`, `useUpdateColumnSetMutation` into the editor.

### E3 — Daily symbols refresh
Added a 24-hour background loop in `MarketDataManager.__init__` using `asyncio.create_task`. Calls `symbols.service.refresh()` once per day from boot.

### E4 — Symbol-search logo URL
`/symbols/search` returned bare TradingView logo filenames. The command palette now constructs the full URL: `https://s3-symbol-logo.tradingview.com/{logo}.svg`, with a fallback letter avatar on error.

### E5 — Chart autosave
Added `auto_save_delay: 5` to TradingView widget options. Removed the manual `onAutoSaveNeeded` subscription — the adapter's `saveChart()` is now called automatically by the TV library.

### E6 — Remove Zerodha login on load
Removed the `useEffect` in `App.tsx` (or equivalent entry point) that eagerly triggered Zerodha auth. Auth now only happens on explicit user action.

## Unresolved questions

None — all 12 items implemented and TypeScript build passes clean.
