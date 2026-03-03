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
  | "unsubscribe_symbols"
  | "create_chart"
  | "modify_chart"
  | "destroy_chart"
  | "resolve_symbol";

// ─── Server → Client Messages ──────────────────────────────────────
export type ServerMessageType =
  | "pong"
  | "screener_session_created"
  | "screener_filter"
  | "screener_values"
  | "full_quote"
  | "quote_update"
  | "chart_series"
  | "symbol_resolved"
  | "chart_update"
  | "broker_status"
  | "broker_login_required"
  | "error";

// ─── Screener Types ────────────────────────────────────────────────
export interface ScreenerFilterRow {
  ticker: string;
  name: string;
  logo?: string;
  v?: Record<string, unknown>;
}

import type { ColumnDef } from "./models";

export interface ScreenerCreateParams {
  source: string;
  columns?: ColumnDef[];
}

export interface ScreenerModifyParams {
  source?: string;
  columns?: ColumnDef[];
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
// ─── Chart Types ───────────────────────────────────────────────────
export interface ChartParams {
  symbol: string;
  interval: string;
  from_date?: string;
  to_date?: string;
}

export interface SymbolResolvedData {
  name: string;
  ticker: string;
  description?: string;
  type: string;
  session: string;
  exchange?: string;
  timezone: string;
  pricescale: number;
  minmov: number;
  has_intraday: boolean;
  has_daily: boolean;
  has_weekly_and_monthly: boolean;
  supported_resolutions: string[];
  logo_urls?: string[];
}

// m: "symbol_resolved", p: [sessionId, metadata]
export type SymbolResolvedResponse = [string, SymbolResolvedData];

export interface ChartCandleData {
  time: number; // UTC Milliseconds
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

// m: "chart_series", p: [sessionId, symbol, interval, candles, seriesId, noData]
export type ChartSeriesResponse = [
  string,
  string,
  string,
  ChartCandleData[],
  string | null,
  boolean,
];

// m: "chart_update", p: [sessionId, symbol, candle]
export type ChartUpdateResponse = [string, string, ChartCandleData];
