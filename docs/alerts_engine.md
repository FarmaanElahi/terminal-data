# Comprehensive Alert System — Implementation Plan

Replace the broker-dependent alert system with an independent, formula-based alert engine. Supports drawing alerts (converted to price/time levels), formula alerts, persistent logs, and multi-channel notifications.

## User Review Required

> [!IMPORTANT]
> **Scale**: Single-server design with in-memory symbol index and batched evaluation. Worker queue deferred to future.

> [!IMPORTANT]
> **Web Push**: Browser-native VAPID — works when tab is closed but browser is running. Mobile push deferred until mobile app exists.

> [!WARNING]
> **Breaking change**: Entire existing [alerts/](file:///Users/farmaan/Public/farmaan/code/terminal/terminal-data/tests/alerts) module (broker proxy) and frontend alert code will be replaced.

---

## Proposed Changes

### Backend Database Models

#### [MODIFY] [models.py](file:///Users/farmaan/Public/farmaan/code/terminal/terminal-data/src/terminal/alerts/models.py)

Complete rewrite with 3 SQLAlchemy models:

**[Alert](file:///Users/farmaan/Public/farmaan/code/terminal/terminal-data/src/web/src/types/alert.ts#1-21)** table:
| Column | Type | Description |
|--------|------|-------------|
| [id](file:///Users/farmaan/Public/farmaan/code/terminal/terminal-data/src/terminal/models.py#9-11) | PK | UUID |
| `user_id` | FK→users | Owner |
| `name` | str | Display name |
| [symbol](file:///Users/farmaan/Public/farmaan/code/terminal/terminal-data/src/terminal/market_feed/store.py#175-179) | str | Ticker (e.g. `NSE:RELIANCE`) |
| `alert_type` | str | `"formula"` or `"drawing"` |
| `status` | str | `"active"`, `"paused"`, `"triggered"`, `"expired"` |
| `trigger_condition` | JSONB | Primary condition — see below |
| `guard_conditions` | JSONB | Additional formula conditions (all must be true) |
| `frequency` | str | `"once"`, `"once_per_minute"`, `"once_per_bar"`, `"end_of_day"` |
| `frequency_interval` | int | Interval in seconds |
| `expiry` | datetime? | Optional auto-expire |
| `trigger_count` | int | Fire count |
| `last_triggered_at` | datetime? | For cooldown |
| `notification_channels` | JSONB? | Per-alert channel IDs (null = no notification, just log) |
| `drawing_id` | str? | TradingView drawing ID (for drawing alerts — links alert to chart drawing) |

**Drawing alert `trigger_condition` format** — stores extracted price/time levels, not the drawing itself:
```json
{
  "drawing_type": "trendline",
  "trigger_when": "crosses_above",
  "points": [
    {"time": 1733788800, "price": 1450.0},
    {"time": 1734912000, "price": 1520.0}
  ]
}
```
For rectangle: `{"drawing_type": "rectangle", "trigger_when": "enters", "top": 1500, "bottom": 1400, "left": 1733788800, "right": 1734912000}`

When the user modifies the drawing in the chart, the frontend sends an update with new extracted price/time levels → alert's `trigger_condition` is updated.

When the user deletes the drawing, the frontend removes or offers to remove the linked alert (matched via `drawing_id`).

**`AlertLog`** table:
| Column | Type | Description |
|--------|------|-------------|
| [id](file:///Users/farmaan/Public/farmaan/code/terminal/terminal-data/src/terminal/models.py#9-11) | PK | UUID |
| `alert_id` | FK→alerts | Which alert fired |
| `user_id` | str | Owner (denormalized) |
| [symbol](file:///Users/farmaan/Public/farmaan/code/terminal/terminal-data/src/terminal/market_feed/store.py#175-179) | str | Symbol at trigger time |
| `triggered_at` | datetime | When it fired |
| `trigger_value` | float | Value that triggered |
| [message](file:///Users/farmaan/Public/farmaan/code/terminal/terminal-data/src/web/src/lib/ws.ts#77-89) | str | Human-readable description |
| `read` | bool | Whether user has seen it |

**`UserNotificationChannel`** table:
| Column | Type | Description |
|--------|------|-------------|
| [id](file:///Users/farmaan/Public/farmaan/code/terminal/terminal-data/src/terminal/models.py#9-11) | PK | UUID |
| `user_id` | FK→users | Owner |
| `channel_type` | str | `"in_app"`, `"telegram"`, `"web_push"` |
| `config` | JSONB | `{"chat_id": "..."}` for Telegram, `{"subscription": {...}}` for Web Push |
| `is_active` | bool | Enabled/disabled |

Notification is per-alert: each alert's `notification_channels` is a list of channel IDs. If `null`/empty, alert still fires and creates a log entry, but no push notification is sent — user checks logs manually.

---

### Alert Engine

#### [NEW] [engine.py](file:///Users/farmaan/Public/farmaan/code/terminal/terminal-data/src/terminal/alerts/engine.py)

```
MarketDataManager.subscribe()  →  debounce 1s  →  batch evaluate by symbol
  │
  For each dirty symbol:
    ├─ Get OHLCV DataFrame (shared across all alerts for this symbol)
    ├─ For each active alert on this symbol:
    │   ├─ Check cooldown
    │   ├─ Evaluate trigger (formula or drawing price levels)
    │   ├─ If trigger TRUE → evaluate guard conditions
    │   ├─ If all guards TRUE → FIRE:
    │   │   ├─ Queue AlertLog insert
    │   │   ├─ Dispatch notifications (if channels configured)
    │   │   ├─ Push toast via WebSocket (in-app)
    │   │   └─ If "once" → set status="triggered"
    └─ Flush log queue every 5s
```

#### [NEW] [drawing.py](file:///Users/farmaan/Public/farmaan/code/terminal/terminal-data/src/terminal/alerts/drawing.py)

Converts stored price/time points to current price level:
- **Trendline**: Linear interpolation between two [(time, price)](file:///Users/farmaan/Public/farmaan/code/terminal/terminal-data/src/web/src/lib/ws.ts#148-161) points, extrapolated to current timestamp
- **Horizontal line**: Fixed price
- **Rectangle**: Box defined by [(top, bottom, left, right)](file:///Users/farmaan/Public/farmaan/code/terminal/terminal-data/src/web/src/lib/ws.ts#148-161) — check if current price+time is inside/outside

---

### Notification Providers

#### [NEW] [notifications/](file:///Users/farmaan/Public/farmaan/code/terminal/terminal-data/src/terminal/notifications/)

| File | Purpose |
|------|---------|
| `base.py` | Abstract `NotificationProvider` interface |
| `in_app.py` | Push `alert_triggered` via WebSocket → shown as toast popup |
| `telegram.py` | Telegram Bot API via httpx |
| `web_push.py` | Web Push VAPID via pywebpush |
| `dispatcher.py` | Routes to provider(s) by channel_type, parallel send |
| [router.py](file:///Users/farmaan/Public/farmaan/code/terminal/terminal-data/src/terminal/charts/router.py) | REST API: list/add/delete channels, verify Telegram, get VAPID key |

---

### Backend API + WebSocket

#### [MODIFY] [alerts/router.py](file:///Users/farmaan/Public/farmaan/code/terminal/terminal-data/src/terminal/alerts/router.py)

Complete rewrite:
- `GET /alerts` — List (filter by status, symbol)
- `POST /alerts` — Create
- `PUT /alerts/{id}` — Update (conditions, frequency, channels, drawing points)
- `DELETE /alerts/{id}` — Delete
- `POST /alerts/{id}/activate` — Re-activate
- `POST /alerts/{id}/pause` — Pause
- `GET /alerts/logs` — Paginated logs
- `DELETE /alerts/by-drawing/{drawing_id}` — Delete alert linked to a drawing

#### [NEW] [alerts/service.py](file:///Users/farmaan/Public/farmaan/code/terminal/terminal-data/src/terminal/alerts/service.py)

CRUD + log queries + engine sync.

#### [MODIFY] [realtime/models.py](file:///Users/farmaan/Public/farmaan/code/terminal/terminal-data/src/terminal/realtime/models.py)

Add `alert_triggered` and `alert_status_changed` WS message types.

#### [MODIFY] [realtime/session.py](file:///Users/farmaan/Public/farmaan/code/terminal/terminal-data/src/terminal/realtime/session.py)

Register session with `AlertEngine` for in-app toast push.

#### [MODIFY] Wire-up files

- [main.py](file:///Users/farmaan/Public/farmaan/code/terminal/terminal-data/src/terminal/main.py) — AlertEngine lifespan
- [api.py](file:///Users/farmaan/Public/farmaan/code/terminal/terminal-data/src/terminal/api.py) — Mount routers
- [config.py](file:///Users/farmaan/Public/farmaan/code/terminal/terminal-data/src/terminal/config.py) — `TELEGRAM_BOT_TOKEN`, VAPID keys
- [dependencies.py](file:///Users/farmaan/Public/farmaan/code/terminal/terminal-data/src/terminal/dependencies.py) — `get_alert_engine()`
- [__init__.py](file:///Users/farmaan/Public/farmaan/code/terminal/terminal-data/src/terminal/__init__.py) — Register models

---

### Frontend Changes

#### [MODIFY] [alert.ts](file:///Users/farmaan/Public/farmaan/code/terminal/terminal-data/src/web/src/types/alert.ts) / [use-alerts.ts](file:///Users/farmaan/Public/farmaan/code/terminal/terminal-data/src/web/src/queries/use-alerts.ts)

Rewrite types and queries for new local alert API.

#### [MODIFY] [alerts-widget.tsx](file:///Users/farmaan/Public/farmaan/code/terminal/terminal-data/src/web/src/components/widgets/alerts-widget.tsx)

Rewrite: lists all alerts with status, shows persistent alert logs (both triggered history and active alerts). No broker dependency.

#### [NEW] Alert creation dialog

Formula editor (reuse Monaco), drawing picker, frequency, per-alert notification channel selector (or "none — log only").

#### [MODIFY] [user-price-alerts.ts](file:///Users/farmaan/Public/farmaan/code/terminal/terminal-data/src/web/src/lib/lightweight/user-price-alerts.ts)

Extend for drawing-alert integration. When user adds alert to a drawing, extract price/time levels and send to backend. When drawing changes, update alert. When drawing deleted, delete/prompt-delete alert.

#### [NEW] Toast notification system

Bottom-left popup toasts for in-app alert notifications. Stackable, dismissible one at a time. Uses existing `sonner` toast library (already imported in [alerts-widget.tsx](file:///Users/farmaan/Public/farmaan/code/terminal/terminal-data/src/web/src/components/widgets/alerts-widget.tsx)). Subscribes to `alert_triggered` WS messages.

#### [NEW] Alert log section (inside alerts widget)

Table showing all triggered alert history with timestamp, symbol, trigger value, message. Filterable by alert, symbol, date. Mark as read.

#### [NEW] Service worker (`public/sw.js`)

Minimal service worker for Web Push notifications.

---

## Verification Plan

### Automated Tests ([tests/alerts/](file:///Users/farmaan/Public/farmaan/code/terminal/terminal-data/tests/alerts))

```bash
uv run pytest tests/alerts/ -v
```

| Test file | Coverage |
|-----------|----------|
| `test_alert_service.py` | CRUD, status transitions, log queries, channel CRUD |
| `test_alert_engine.py` | Formula eval, guards, drawing alerts (trendline interpolation, rectangle), frequency throttling, auto-deactivation |
| `test_notifications.py` | In-app (mock WS), Telegram (mock httpx), Web Push (mock pywebpush) |
| `test_alerts_api.py` | REST endpoints, auth, log pagination, drawing-linked delete |

### Manual Verification

1. Create alert → verify log appears when condition met
2. Verify toast popup on bottom-left in UI
3. Verify Telegram delivery
4. Verify `"once"` auto-deactivates
5. Verify drawing-linked alert updates when drawing moves
