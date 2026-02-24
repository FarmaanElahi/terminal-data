/* WebSocket message types */

export interface WSMessage {
  m: string;
  p?: unknown[];
}

// ─── Client → Server Messages ──────────────────────────────────────
export type ClientMessageType =
  | "ping"
  | "create_screener"
  | "modify_screener"
  | "destroy_screener"
  | "create_quote_session"
  | "subscribe_symbols"
  | "unsubscribe_symbols";

// ─── Server → Client Messages ──────────────────────────────────────
export type ServerMessageType =
  | "pong"
  | "screener_session_created"
  | "screener_filter"
  | "screener_values"
  | "full_quote"
  | "quote_update"
  | "error";

// ─── Screener Types ────────────────────────────────────────────────
export interface ScreenerFilterRow {
  ticker: string;
  name: string;
  logo_id?: string;
}

export interface ScreenerCreateParams {
  source: string;
  column_set_id: string;
}

export interface ScreenerModifyParams {
  source?: string;
  column_set_id?: string;
  filter_active?: boolean;
}

// column_id → values array (one per ticker, in same order as filter)
export type ScreenerValues = Record<string, unknown[]>;

// ─── Quote Types ───────────────────────────────────────────────────
export interface QuoteData {
  open?: number;
  high?: number;
  low?: number;
  close?: number;
  volume?: number;
  change?: number;
  change_percent?: number;
}
