# State Management Refactor: Server-Side Layout + TanStack Query — IMPLEMENTED

## Status: Complete

## Architecture

```
Server state (lists, columnSets, conditionSets, formulas)
  → TanStack Query cache (populated at boot via queryClient.setQueryData)
  → mutated via optimistic mutations with onMutate / onError / onSettled

Layout state (layouts tree, activeLayoutId, theme, channelContexts)
  → Zustand with persist (localStorage as fallback)
  → synced to server via debounced LayoutSync component (1s debounce)

Auth state (token, user, isAuthenticated, isBooted, symbols, editorConfig)
  → Zustand only (symbols + editorConfig are static boot data, never mutated)
```

## What Was Changed

### Backend
- **New**: `src/terminal/preferences/` module (`models.py`, `service.py`, `router.py`, `__init__.py`)
- **New**: Migration `2026-03-01_6b7ff0144b9f_add_user_preferences.py`
- `src/terminal/api.py` — includes `preferences_router`
- `src/terminal/boot.py` — includes `preferences: {layout, settings}` in response
- `src/terminal/database/manage.py` — imports `UserPreferences`

### Frontend — Query Infrastructure
- **New**: `src/web/src/queries/query-keys.ts`
- **New**: `src/web/src/queries/use-lists.ts` (CRUD + flag mutations)
- **New**: `src/web/src/queries/use-column-sets.ts`
- **New**: `src/web/src/queries/use-condition-sets.ts`
- **New**: `src/web/src/queries/use-formulas.ts`
- **New**: `src/web/src/queries/use-layout.ts`
- `src/web/src/lib/api.ts` — `preferencesApi`, extended `BootResponse`

### Frontend — Stores
- `src/web/src/stores/auth-store.ts` — slimmed (removed lists/columnSets/conditionSets/formulas mutations); kept symbols+editorConfig as static boot data; all actions accept `queryClient`
- `src/web/src/stores/layout-store.ts` — added `initializeLayout()`

### Frontend — Components
- **New**: `src/web/src/components/layout/layout-sync.tsx`
- `src/web/src/app/providers.tsx` — updated QueryClient config, passes queryClient to loadBoot, mounts LayoutSync
- `src/web/src/app/routes/login.tsx` — passes queryClient
- `src/web/src/app/routes/register.tsx` — passes queryClient
- `src/web/src/components/layout/header.tsx` — passes queryClient to logout
- `src/web/src/components/widgets/screener-widget.tsx` — TQ hooks
- `src/web/src/components/widgets/watchlist-widget.tsx` — TQ hooks
- `src/web/src/components/widgets/list-selection-dialog.tsx` — TQ hooks
- `src/web/src/components/widgets/create-list-dialog.tsx` — TQ hooks
- `src/web/src/components/widgets/column-editor.tsx` — TQ hooks
- `src/web/src/components/layout/app-sidebar.tsx` — TQ hooks
- `src/web/src/components/screener/screener-table.tsx` — TQ hooks
- `src/web/src/app/routes/screener.tsx` — TQ hooks
- `src/web/src/components/dashboard/layout-engine.tsx` — useShallow
- `src/web/src/components/dashboard/layout-node.tsx` — memo
- `src/web/src/components/dashboard/pane-container.tsx` — boolean derivation

## Verification

```bash
# Backend
uv run terminal database upgrade
uv run fastapi dev src/terminal/main.py
curl -H "Authorization: Bearer <token>" http://localhost:8000/api/v1/preferences

# Frontend
npm run build  # passes ✓
```
