import type { ColumnDef } from "@/types/models";

export type MiniChartViewMode = "grid" | "list";
export type MiniChartSortDirection = "asc" | "desc";
export type MiniChartScaleMode = "linear" | "log";
export type MiniChartMAType = "ema" | "sma";

export interface MiniChartMAConfig {
  id: string;
  length: number;
  color: string;
  enabled: boolean;
  maType: MiniChartMAType;
}

export interface MiniChartSettings {
  listId: string | null;
  viewMode: MiniChartViewMode;
  columns: ColumnDef[];
  headerColumnIds: string[];
  sortKey: string;
  sortDirection: MiniChartSortDirection;
  timeframe: string;
  scaleMode: MiniChartScaleMode;
  maConfigs: MiniChartMAConfig[];
  gridColumns: number;
}

export interface MiniChartValueItem {
  colId: string;
  name: string;
  value: unknown;
}

export interface MiniChartBar {
  time: number; // Unix epoch milliseconds
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}
