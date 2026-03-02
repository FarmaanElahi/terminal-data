# Plan: Watchlist/Screener Sections

## Context
Add TradingView-style sections to the watchlist and screener widgets. Sections are stored inline in the `symbols` array as `###<Section Name>` entries (e.g. `["###Tech", "NASDAQ:AAPL", "NASDAQ:MSFT", "###Energy", "NSE:ONGC"]`). Sections only apply to **simple** lists; combo and system lists strip `###` entries and display flat.

When sorting is enabled in the screener, sort happens **within each section independently** — section boundaries are never crossed.

---

## Critical Bug Fix (prerequisite)
`append_symbols` in `service.py` was converting `lst.symbols` to a `set`, destroying order. Fixed to preserve order, appending new symbols at end.

---

## Files Modified

### Backend

**`src/terminal/lists/service.py`**
- Fixed `append_symbols` to preserve ordering
- Added `set_symbols(session, lst, data)` service function: replaces entire symbols array
- Fixed `get_symbols` / `get_symbols_async` for simple lists: filter out `###` entries
- For combo `get_symbols`: filter `###` from source list symbols too

**`src/terminal/lists/router.py`**
- Added `PUT /{id}/symbols` endpoint: accepts `SymbolsUpdate`, simple lists only, calls `set_symbols`

### Frontend

**`src/web/src/lib/api.ts`**
- Added `setSymbols: (id, symbols) => api.put(...)` to `listsApi`

**`src/web/src/queries/use-lists.ts`**
- Added `useSetSymbolsMutation()` with optimistic update

**`src/web/src/components/widgets/watchlist-widget.tsx`**
- Parse `symbols` into `ParsedItem[]` (`section` | `symbol`)
- Render section headers with hover-reveal delete (×) button (simple lists only)
- "Add Section" button (Minus icon) in header bar (simple lists only)
- Inline input for new section name, committed on Enter/blur, cancelled on Escape
- `isActive` check skips `###` entries

**`src/web/src/components/widgets/screener-widget.tsx`**
- `sectionMap` + `sectionOrder` computed from `selectedList.symbols` (simple lists only)
- Section-aware `sortedIndices`: group by section, sort within each group, flatten in section order
- `displayItems` array: `{ type: 'symbol', tickerIndex }` | `{ type: 'section', name }` — inserts section headers at group boundaries
- Virtualizer uses `displayItems.length`
- Section rows rendered as non-interactive `<tr>` with `bg-muted/40` styling
- Keyboard nav (`ArrowUp`/`ArrowDown`) skips section rows
- Channel symbol sync uses `displayItems` to find display index

---

## Data Flow

```
DB symbols: ["###Tech", "AAPL", "MSFT", "###Energy", "ONGC"]
                ↓ get_symbols_async (filters ### out)
Backend sees: ["AAPL", "MSFT", "ONGC"]
                ↓ screener_filter WS message
Frontend tickers: [{ ticker: "AAPL" }, { ticker: "MSFT" }, { ticker: "ONGC" }]
                ↓ sectionMap (from useListsQuery)
sectionMap: AAPL→"Tech", MSFT→"Tech", ONGC→"Energy"
                ↓ sortedIndices (within-section sort)
displayItems: [section:"Tech", sym:AAPL, sym:MSFT, section:"Energy", sym:ONGC]
```

---

## Section UI/Styling
- Section header row: `bg-muted/40 px-3 h-7 flex items-center`
- Label: `text-[10px] uppercase tracking-wider font-semibold text-muted-foreground`
- Delete button: small `×` on hover, only in watchlist (screener sections are read-only)
- "Add Section" button: `Minus` icon in watchlist header bar

## Unresolved Questions
- If user renames a section in watchlist (not yet planned) — should that be inline edit or modal?
- Screener: show empty section headers (when all symbols filtered out) or hide them?
