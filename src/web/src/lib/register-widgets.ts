/**
 * Bootstrap file that registers all available widgets.
 * Import this once in the app entry point (e.g., main.tsx or providers.tsx).
 */
import { registerWidget } from "@/lib/widget-registry";
import { ScreenerWidget } from "@/components/widgets/screener-widget";
import { WatchlistWidget } from "@/components/widgets/watchlist-widget";
import { ChartWidget } from "@/components/widgets/chart-widget";
import { CommunityFeedWidget } from "@/components/widgets/community-feed-widget";
import { CommunityFeedGlobalWidget } from "@/components/widgets/community-feed-global-widget";
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
  type: "watchlist",
  title: "Watchlist",
  icon: "list",
  component: WatchlistWidget,
  defaultSettings: { listId: null },
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
