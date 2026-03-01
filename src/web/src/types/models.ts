/* Domain model interfaces — matches backend Pydantic schemas */

export interface User {
  id: string;
  username: string;
  is_active: boolean;
}

export type ListType = "simple" | "color" | "combo" | "system";

export interface List {
  id: string;
  user_id: string;
  name: string;
  type: ListType;
  color: string | null;
  symbols: string[];
  source_list_ids: string[] | null;
}

export interface Formula {
  id: string;
  user_id: string;
  name: string;
  body: string;
  params: Record<string, number> | null;
}

export type ConditionalLogic = "and" | "or";
export type TimeframeMode = "context" | "fixed" | "mixed";
export type Timeframe = "D" | "W" | "M" | "Y";

export interface Condition {
  formula: string;
  timeframe: Timeframe;
}

export interface ConditionSet {
  id: string;
  user_id: string;
  name: string;
  conditions: Condition[];
  conditional_logic: ConditionalLogic;
  timeframe: TimeframeMode;
  timeframe_value: Timeframe | null;
}

export type ColumnType = "value" | "condition";
export type FilterState = "active" | "inactive" | "off";
export type ValueType = "field" | "formula";
export type FieldDataType = "numeric" | "string" | "date";
export type EvaluateAs = "true" | "gt" | "lt" | "in_between" | "rank";
export type FilterEvaluateOn =
  | "now"
  | "x_bar_ago"
  | "within_x_bars"
  | "x_bar_in_row";

export interface ConditionDef {
  name?: string | null;
  formula: string;
  evaluate_as?: EvaluateAs | null;
  evaluate_as_params?: unknown[] | null;
}

export interface ColumnDef {
  // ── Core ──
  id: string;
  name: string;
  visible: boolean;
  type: ColumnType;
  filter: FilterState;

  // ── Value Column ──
  value_type?: ValueType | null;
  value_field_data_type?: FieldDataType | null;
  value_formula?: string | null;
  value_formula_tf?: Timeframe | null;
  value_formula_x_bar_ago?: number | null;
  // value filter
  value_formula_filter_enabled?: boolean | null;
  value_formula_filter_op?: "gt" | "lt" | null;
  value_formula_filter_params?: unknown[] | null;
  value_formula_filter_evaluate_on?: FilterEvaluateOn | null;
  value_formula_filter_evaluate_on_params?: unknown[] | null;
  value_formula_refresh_interval?: number | null;

  // ── Condition Column ──
  conditions?: ConditionDef[] | null;
  conditions_logic?: "and" | "or" | null;
  condition_tf_mode?: TimeframeMode | null;
  conditions_tf?: Timeframe | null;
  condition_value_x_bar_ago?: number | null;

  // ── Display ──
  display_color?: string | null;
  display_column_width?: number | null;
  sort?: "asc" | "desc" | null;
  display_numeric_positive_color?: string | null;
  display_numeric_negative_color?: string | null;
  display_numeric_prefix?: string | null;
  display_numeric_suffix?: string | null;
  display_numeric_show_positive_sign?: boolean | null;
  display_numeric_max_decimal?: number | null;
}

export interface ColumnSet {
  id: string;
  user_id: string;
  name: string;
  columns: ColumnDef[];
}

export interface Symbol {
  ticker: string;
  name: string;
  type: string;
  market: string;
  exchange: string;
  isin: string | null;
  logo_id: string | null;
  logo: string | null;
}

export interface SearchMetadata {
  markets: string[];
  types: string[];
  indexes: string[];
}

// ─── StockTwits Community Feed ────────────────────────────────────────

export interface StockTwitsUser {
  id: number;
  username: string;
  name: string;
  avatar_url_ssl?: string;
}

export interface StockTwitsMessage {
  id: number;
  body: string;
  created_at: string;
  user: StockTwitsUser;
  symbols?: { symbol: string; title: string }[];
  likes?: { total: number };
  entities?: { sentiment?: { basic: "Bullish" | "Bearish" } };
}

export interface StockTwitsFeedResponse {
  messages?: StockTwitsMessage[];
  data?: StockTwitsMessage[];
}
