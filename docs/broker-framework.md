# Broker Integration Framework

## Status

This document reflects the **implemented state** as of **March 3, 2026**.

The terminal now supports a generic multi-broker framework with:

- Provider adapters (`upstox`, `kite`)
- Multiple accounts per provider
- Per-adapter token validity checks (including expiration/remote validation)
- Provider defaults per `(capability, market)` with fallback behavior
- Broker account management UI (add account, view owner, remove account)

## Provider Matrix

| Provider | Markets | Capabilities                                          | Notes                                                                                           |
| -------- | ------- | ----------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| `upstox` | `india` | `realtime_candles`                                    | Used for realtime candle feed/client integration                                                |
| `kite`   | `india` | `alerts`, `order_management`, `positions`, `holdings` | Alerts fully implemented (see [alerts.md](alerts.md)); order execution flow not implemented yet |

## Architecture

### Core Flow

1. Each provider implements `BrokerAdapter`.
2. Registry returns configured providers.
3. User credentials are stored in `broker_credentials` (multiple rows per provider allowed).
4. Active credential selection always checks token validity via adapter.
5. Realtime provider selection uses user default if available; otherwise first active provider.

### Adapter Contract

`src/terminal/broker/adapter.py`:

- `build_auth_url()`
- `exchange_code(code)`
- `is_configured()`
- `create_feed(token)` (optional)
- `create_candle_provider(token, feed)` (optional)
- `validate_token(token)` (required)
- `fetch_account_info(token)` (optional, used for account metadata/profile)

New capability enums include:

- `realtime_candles`
- `alerts`
- `order_management`
- `positions`
- `holdings`

### Token Validation

All active-token resolution paths now validate tokens through adapter methods:

- `GET /broker`
- `GET /broker/{provider_id}/status`
- WebSocket realtime bootstrap provider selection
- Account delete flow when selecting the next active credential

Provider behavior:

- Upstox:
  - Checks JWT `exp` locally when present
  - Validates remotely via `GET https://api.upstox.com/v2/user/profile`
- Kite:
  - Validates by calling `GET https://api.kite.trade/user/profile`

Validation is cached briefly in-memory per adapter instance to reduce repeated calls.

### Multi-Provider Selection Logic

For each market/capability:

1. Collect configured providers supporting that pair.
2. Keep only providers with a currently valid token.
3. Check `broker_defaults` for user preference.
4. If preferred provider is active, use it.
5. Otherwise use the first active provider.

This is implemented in `select_market_providers()` in `src/terminal/realtime/handler.py`.

## Backend Implementation

### Registry and Feed Pool

- `src/terminal/broker/registry.py` registers `UpstoxAdapter` and `KiteAdapter`.
- `src/terminal/broker/feed_registry.py` is keyed by `(user_id, provider_id)`.
- `src/terminal/candles/feed_registry.py` is a compatibility re-export.

### Account Metadata and Profile Storage

`broker_credentials` now stores:

- `account_id`
- `account_label`
- `account_owner`
- `profile_raw` (JSON payload from provider profile endpoint)

On OAuth callback, account info is fetched and stored.

For legacy rows missing owner/label/id, `GET /broker` lazily backfills metadata via `fetch_account_info()` and persists it.

### API Endpoints

`src/terminal/broker/router.py` exposes:

- `GET /broker`
- `GET /broker/defaults`
- `PUT /broker/defaults`
- `GET /broker/{provider_id}/auth-url`
- `POST /broker/{provider_id}/callback`
- `GET /broker/{provider_id}/status`
- `DELETE /broker/{provider_id}/accounts/{credential_id}`

`GET /broker` returns per-provider:

- `provider_id`, `display_name`, `markets`, `capabilities`
- `connected`, `login_required`
- `accounts[]` with `account_id`, `account_label`, `account_owner`
- `active_account_key`

### Realtime Integration

- WebSocket sends `broker_status` snapshot on connect.
- Sends `broker_login_required` for providers requiring login.
- `RealtimeSession.restart_broker_feed(provider_id, token)` replaces provider-specific restart paths.
- Session keeps `_feed_refs: set[str]` for provider feed lifecycle.

## Frontend Implementation

### API + Hooks

- `src/web/src/lib/api.ts` has generic `brokerApi` methods for list/defaults/auth/callback/status/remove.
- `src/web/src/hooks/use-brokers.ts` handles queries, default mutation, account removal, popup login.
- `src/web/src/hooks/use-broker-gate.ts` resolves feature gating by capability/market with default-aware connected-provider selection.

### Callback Route

- Route: `/broker/:providerId/callback`
- Callback page reads either:
  - `code` (Upstox-style)
  - `request_token` (Kite-style)
- Both are sent as `code` in backend callback payload.

### Broker Widget (UI)

`src/web/src/components/widgets/broker-widget.tsx` provides:

- Top-level **Add Broker Account** action row (one button per configured provider)
- Per-provider **Add Account** button
- Account list showing account label/id and **Owner**
- Active account badge
- Remove account action (trash icon)
- Default selection controls for overlapping capability+market pairs

If the server has zero configured providers, widget shows:

- "No Broker Providers Available"
- "Refresh Providers" action

This is expected behavior when broker OAuth env config is missing.

### Login Prompt Dialog

`src/web/src/components/layout/broker-login-dialog.tsx`:

- Listens to `broker_login_required`
- Prompts provider-specific login
- Uses consistent design-system buttons/dialog styles

## OAuth and Config

`src/terminal/config.py` settings:

- Upstox:
  - `upstox_api_key`
  - `upstox_api_secret`
  - `upstox_redirect_uri` (example: `/broker/upstox/callback`)
- Kite:
  - `kite_api_key`
  - `kite_api_secret`
  - `kite_redirect_uri` (example: `/broker/kite/callback`)

Provider appears in `/broker` only when corresponding adapter `is_configured()` is true.

## Database Migrations

Broker-related revisions currently include:

- `2026-03-03_3863cf3354ad_add_broker_credentials.py`
- `2026-03-03_9a9f6f4f5f10_add_broker_defaults.py`
- `2026-03-03_b42f0d55f8da_add_broker_account_fields.py`
- `2026-03-03_d8c6a4f91be3_add_broker_profile_raw.py`
- `2026-03-03_5d6d6d8d0b2f_ensure_broker_profile_raw_column.py`

The latest migration chain keeps `profile_raw` forward-safe for already-migrated environments.

## User Flows

### Add a New Broker Account

1. Add/open the **Broker Accounts** widget.
2. Click **Add Broker Account** (top row) or provider-level **Add Account**.
3. Complete provider OAuth.
4. Callback stores token + profile metadata.
5. Widget refresh shows the new account and owner name.

### Remove a Broker Account

1. In Broker Accounts widget, click trash icon next to account.
2. Confirm removal.
3. Backend deletes credential and re-evaluates active valid account.
4. Realtime feed/session status is updated accordingly.

### Set Default Provider

When multiple providers overlap for same capability+market:

1. Click **Set Default** in widget.
2. `PUT /broker/defaults` stores preference.
3. Realtime/provider resolution uses that provider if active; else first active fallback.

## Adding Another Broker

To add a new provider (for example IBKR):

1. Create `src/terminal/broker/adapters/<provider>.py` implementing `BrokerAdapter`.
2. Register in `src/terminal/broker/registry.py`.
3. Implement token validation and account-profile fetch.
4. Add config keys and `is_configured()` logic.
5. If realtime candles are supported, implement feed/provider wiring.
6. Frontend should auto-discover provider through `GET /broker`.
