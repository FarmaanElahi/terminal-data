/* API request/response types */
import type {
  User,
  List,
  Formula,
  ConditionSet,
  ColumnSet,
  ColumnDef,
  Symbol,
} from "./models";

// ─── Auth ──────────────────────────────────────────────────────────
export interface LoginRequest {
  username: string;
  password: string;
}

export interface RegisterRequest {
  username: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

// ─── Symbols ───────────────────────────────────────────────────────
export interface SymbolSearchParams {
  q?: string;
  market?: string;
  type?: string;
  index?: string;
  limit?: number;
}

export interface SearchResultResponse {
  data: Symbol[];
  total: number;
}

// ─── Lists ─────────────────────────────────────────────────────────
export interface ListCreate {
  name: string;
  type: "simple" | "color" | "combo";
  color?: string;
  symbols?: string[];
  source_list_ids?: string[];
}

export interface ListUpdate {
  name?: string;
  color?: string;
  symbols?: string[];
}

export interface AppendSymbolsRequest {
  symbols: string[];
}

export interface ScanResult {
  columns: string[];
  values: Record<string, unknown[]>;
}

// ─── Formula ───────────────────────────────────────────────────────
export interface FormulaCreate {
  name: string;
  body: string;
  params?: Record<string, number>;
}

export interface FormulaValidateRequest {
  body: string;
  symbol: string;
  timeframe?: string;
}

export interface FormulaValidateResponse {
  valid: boolean;
  result_type?: string;
  last_value?: unknown;
  row_count?: number;
  error?: string;
}

export interface EditorConfig {
  keywords: string[];
  functions: string[];
  fields: string[];
}

// ─── Conditions ────────────────────────────────────────────────────
export interface ConditionSetCreate {
  name: string;
  conditions: Array<{ formula: string; timeframe: string }>;
  conditional_logic: "and" | "or";
  timeframe: "context" | "fixed" | "mixed";
  timeframe_value?: string;
}

export type ConditionSetUpdate = Partial<ConditionSetCreate>;

// ─── Columns ───────────────────────────────────────────────────────
export interface ColumnSetCreate {
  name: string;
  columns: ColumnDef[];
}

export type ColumnSetUpdate = Partial<ColumnSetCreate>;

// ─── Re-exports for convenience ────────────────────────────────────
export type { User, List, Formula, ConditionSet, ColumnSet, Symbol };
