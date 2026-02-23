/* Domain model interfaces — matches backend Pydantic schemas */

export interface User {
  id: string;
  username: string;
  is_active: boolean;
}

export type ListType = "simple" | "color" | "combo";

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

export type ColumnType = "value" | "condition" | "tag";
export type FilterState = "active" | "inactive" | "off";

export interface ColumnDef {
  id: string;
  name: string;
  type: ColumnType;
  formula: string;
  timeframe: Timeframe;
  bar_ago: number;
  visible: boolean;
  condition_id: string | null;
  filter: FilterState;
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
}

export interface SearchMetadata {
  markets: string[];
  types: string[];
  indexes: string[];
}
