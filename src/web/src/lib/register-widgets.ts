/**
 * Bootstrap file that registers all available widgets.
 * Import this once in the app entry point (e.g., main.tsx or providers.tsx).
 */
import { registerWidget } from "@/lib/widget-registry";
import { ScreenerWidget } from "@/components/widgets/screener-widget";
import { ChartWidget } from "@/components/widgets/chart-widget";
import { CommunityFeedWidget } from "@/components/widgets/community-feed-widget";
import { CommunityFeedGlobalWidget } from "@/components/widgets/community-feed-global-widget";
import { BubbleChartWidget } from "@/components/widgets/bubble-chart-widget";
import { BrokerWidget } from "@/components/widgets/broker-widget";
import { AlertsWidget } from "@/components/widgets/alerts-widget";
import { MiniChartWidget } from "@/components/widgets/mini-chart-widget";
import type { ColumnDef } from "@/types/models";

export const DEFAULT_SCREENER_COLUMNS: ColumnDef[] = [
  {
    id: "col_price",
    name: "Price",
    visible: true,
    type: "value",
    filter: "off",
    value_type: "formula",
    value_formula: "C",
    value_formula_tf: "D",
    value_formula_x_bar_ago: 0,
    display_column_width: 100,
    display_color: "#ffffff",
  },
  {
    id: "col_change_pct",
    name: "Change%",
    visible: true,
    type: "value",
    filter: "off",
    value_type: "formula",
    value_formula: "(C/C.1 - 1) * 100",
    value_formula_tf: "D",
    value_formula_x_bar_ago: 0,
    display_column_width: 100,
    display_color: "#ffffff",
    display_numeric_show_positive_sign: true,
    display_numeric_max_decimal: 2,
    display_numeric_suffix: "%",
  },
  {
    id: "col_volume",
    name: "Volume",
    visible: true,
    type: "value",
    filter: "off",
    value_type: "formula",
    value_formula: "V",
    value_formula_tf: "D",
    value_formula_x_bar_ago: 0,
    display_column_width: 100,
    display_color: "#ffffff",
  },
];

registerWidget({
  type: "screener",
  title: "Screener",
  icon: "table-2",
  component: ScreenerWidget,
  defaultSettings: { listId: null, columns: DEFAULT_SCREENER_COLUMNS },
});

registerWidget({
  type: "chart",
  title: "Chart",
  icon: "bar-chart-3",
  component: ChartWidget,
  defaultSettings: { symbol: "NSE:RELIANCE", interval: "D" },
});

registerWidget({
  type: "community_feed",
  title: "Community Feed",
  icon: "message-square",
  component: CommunityFeedWidget,
  defaultSettings: { symbol: null, feed: "trending" },
});

registerWidget({
  type: "community_feed_global",
  title: "Global Feed",
  icon: "globe",
  component: CommunityFeedGlobalWidget,
  defaultSettings: { feed: "trending" },
});

registerWidget({
  type: "bubble_chart",
  title: "Bubble Chart",
  icon: "circle-dot",
  component: BubbleChartWidget,
  defaultSettings: {
    listId: null,
    xColumn: {
      id: "bubble_x",
      name: "Change%",
      visible: true,
      type: "value",
      filter: "off",
      value_type: "formula",
      value_formula: "(C/C.1-1)*100",
      value_formula_tf: "D",
      value_formula_x_bar_ago: 0,
    },
    yColumn: {
      id: "bubble_y",
      name: "Volume",
      visible: true,
      type: "value",
      filter: "off",
      value_type: "formula",
      value_formula: "V",
      value_formula_tf: "D",
      value_formula_x_bar_ago: 0,
    },
    sizeColumn: {
      id: "bubble_size",
      name: "Closing Range%",
      visible: true,
      type: "value",
      filter: "off",
      value_type: "formula",
      value_formula: "(C-L)/(H-L)*100",
      value_formula_tf: "D",
      value_formula_x_bar_ago: 0,
    },
  },
});

registerWidget({
  type: "broker",
  title: "Broker Accounts",
  icon: "link",
  component: BrokerWidget,
  defaultSettings: {},
});

registerWidget({
  type: "alerts",
  title: "Alerts",
  icon: "bell",
  component: AlertsWidget,
  defaultSettings: {},
});

registerWidget({
  type: "mini_chart",
  title: "Mini Chart",
  icon: "layout-grid",
  component: MiniChartWidget,
  defaultSettings: {
    listId: null,
    viewMode: "grid",
    columns: DEFAULT_SCREENER_COLUMNS,
    headerColumnIds: [
      DEFAULT_SCREENER_COLUMNS[0].id,
      DEFAULT_SCREENER_COLUMNS[1].id,
      DEFAULT_SCREENER_COLUMNS[2].id,
    ],
    sortKey: "ticker",
    sortDirection: "asc",
    timeframe: "1D",
    scaleMode: "linear",
    maConfigs: [
      { id: "ema20", maType: "ema", length: 20, color: "#3B82F6", enabled: true },
      { id: "sma50", maType: "sma", length: 50, color: "#EC4899", enabled: false },
    ],
    gridColumns: 3,
  },
});
