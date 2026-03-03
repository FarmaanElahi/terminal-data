# Alerts

## Status

This document reflects the **implemented state** as of **March 4, 2026**.

The terminal supports price alerts via the [Kite Connect Alerts API](https://kite.trade/docs/connect/v3/alerts/). Alerts are stored entirely on Kite's side — the terminal acts as a stateless proxy with a unified API layer.

## Provider Support

| Provider | Capability | Status                                      |
| -------- | ---------- | ------------------------------------------- |
| `kite`   | `alerts`   | ✅ Full CRUD (list, create, modify, delete) |

## Architecture

```
┌──────────────┐     ┌─────────────────┐     ┌──────────────────────┐
│  Chart Widget │────▶│  POST /alerts   │────▶│  KiteAdapter         │
│  context menu │     │  (unified API)  │     │  .create_alert()     │
├──────────────┤     ├─────────────────┤     │  → api.kite.trade    │
│ Alerts Widget │────▶│  GET /alerts    │     │    /alerts           │
│  list/delete  │     │  DELETE /alerts │     └──────────────────────┘
└──────────────┘     └─────────────────┘
```

### Backend

**Files:**

| File                                   | Purpose                                                                                            |
| -------------------------------------- | -------------------------------------------------------------------------------------------------- |
| `src/terminal/alerts/models.py`        | Pydantic models: `AlertResponse`, `AlertCreateRequest`, `AlertModifyRequest`, `AlertDeleteRequest` |
| `src/terminal/alerts/router.py`        | Unified `/alerts` CRUD router, aggregates across all providers supporting `Capability.ALERTS`      |
| `src/terminal/broker/adapter.py`       | Base `BrokerAdapter` class with optional alert methods                                             |
| `src/terminal/broker/adapters/kite.py` | Kite implementation — form-urlencoded requests to `api.kite.trade/alerts`                          |
| `src/terminal/api.py`                  | Registers the alerts router                                                                        |

### Frontend

**Files:**

| File                                               | Purpose                                                                                                           |
| -------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| `src/web/src/types/alert.ts`                       | TypeScript interfaces matching backend models                                                                     |
| `src/web/src/lib/api.ts`                           | `alertsApi` namespace with CRUD methods                                                                           |
| `src/web/src/queries/query-keys.ts`                | `alerts` query key                                                                                                |
| `src/web/src/queries/use-alerts.ts`                | React Query hooks: `useAlertsQuery`, `useCreateAlertMutation`, `useModifyAlertMutation`, `useDeleteAlertMutation` |
| `src/web/src/components/widgets/alerts-widget.tsx` | Alert management widget                                                                                           |
| `src/web/src/components/widgets/chart-widget.tsx`  | Chart right-click context menu + alert line rendering                                                             |
| `src/web/src/lib/register-widgets.ts`              | Registers `alerts` widget (bell icon)                                                                             |

## API Endpoints

All endpoints are under `/api/v1/alerts` and require authentication.

### List Alerts

```
GET /api/v1/alerts
```

Returns alerts from **all** connected providers that support `Capability.ALERTS`. If a provider's token is invalid, that provider is silently skipped.

**Response:** `AlertResponse[]`

### Create Alert

```
POST /api/v1/alerts
```

**Body (`AlertCreateRequest`):**

| Field               | Type   | Required | Default             | Description                                             |
| ------------------- | ------ | -------- | ------------------- | ------------------------------------------------------- |
| `provider_id`       | string | ✅       | —                   | Provider to create the alert on (e.g. `"kite"`)         |
| `name`              | string | ✅       | —                   | Alert name (min 1 char); fallback generated if empty    |
| `type`              | string |          | `"simple"`          | `"simple"` or `"ato"` (Alert Triggers Order)            |
| `lhs_exchange`      | string | ✅       | —                   | Exchange for the instrument (e.g. `"NSE"`, `"INDICES"`) |
| `lhs_tradingsymbol` | string | ✅       | —                   | Trading symbol (e.g. `"RELIANCE"`, `"NIFTY 50"`)        |
| `lhs_attribute`     | string |          | `"LastTradedPrice"` | Price attribute to monitor                              |
| `operator`          | string | ✅       | —                   | `">="`, `"<="`, `">"`, `"<"`, `"=="`                    |
| `rhs_type`          | string |          | `"constant"`        | `"constant"` or `"instrument"`                          |
| `rhs_constant`      | float  |          | —                   | Target price (required when `rhs_type` is `"constant"`) |
| `rhs_exchange`      | string |          | —                   | RHS exchange (when `rhs_type` is `"instrument"`)        |
| `rhs_tradingsymbol` | string |          | —                   | RHS trading symbol (when `rhs_type` is `"instrument"`)  |

**Response:** `AlertResponse`

### Modify Alert

```
PUT /api/v1/alerts/{alert_id}
```

**Body (`AlertModifyRequest`):** Same fields as create, all optional except `provider_id`. Only provided fields are updated.

**Response:** `AlertResponse`

### Delete Alerts

```
DELETE /api/v1/alerts
```

**Body (`AlertDeleteRequest`):**

| Field         | Type     | Required | Description                       |
| ------------- | -------- | -------- | --------------------------------- |
| `provider_id` | string   | ✅       | Provider the alerts belong to     |
| `uuids`       | string[] | ✅       | One or more alert UUIDs to delete |

**Response:** `{ "status": "success" }`

## Chart Integration

### Context Menu

Right-clicking on the chart shows two alert options at the top of the context menu:

- **"Alert above {price}"** — creates an alert with `operator: ">="` at the right-clicked price
- **"Alert below {price}"** — creates an alert with `operator: "<="` at the right-clicked price

The alert is created for the current chart symbol (e.g. `NSE:RELIANCE`), using `LastTradedPrice` as the monitored attribute. Provider is hardcoded to `"kite"`.

### Alert Lines

Enabled alerts with `rhs_type: "constant"` matching the current chart symbol are drawn as dashed horizontal lines using TradingView's `createShape('horizontal_line')`:

- **Green (`#22C55E`)** — alerts with `>=` or `>` operator (above price)
- **Red (`#EF4444`)** — alerts with `<=` or `<` operator (below price)

Lines show the alert name on the right side with the price label. They are non-interactive (locked, non-selectable) and are not persisted in chart state.

Lines automatically redraw when:

- The alert data changes (create, modify, delete)
- The chart symbol changes
- The chart becomes ready (handles page refresh race condition via `chartReady` state)

## Alerts Widget

The Alerts Widget is available in the widget picker under the **bell** icon. It displays:

- Scrollable list of all alerts sorted by status (enabled first) then by creation date
- Each alert shows: bell icon (amber if enabled, muted if disabled), name, status badge, symbol, operator, price, and trigger count
- **Delete button** on each row (with confirmation)
- **Broker login prompt** if no alert-capable broker is connected
- **Empty state** guiding users to right-click on charts

## Kite API Notes

- Kite expects **form-urlencoded** request bodies (not JSON)
- All form values must be stringified
- The `name` field must be at least 1 character; the router generates a fallback name (`"{tradingsymbol} alert"`) if empty
- Alerts are stored on Kite's side — no local database tables or migrations needed
- Token validation is performed before every API call via `adapter.validate_token()`

## Adding a New Alert Provider

To add alert support for another broker:

1. **Adapter** — implement `list_alerts`, `create_alert`, `modify_alert`, `delete_alerts` in your adapter class
2. **Capability** — add `Capability.ALERTS` to the adapter's capabilities list
3. **Frontend** — update the chart context menu if the `provider_id` needs to be dynamically resolved (currently hardcoded to `"kite"`)
