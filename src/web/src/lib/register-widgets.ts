/**
 * Bootstrap file that registers all available widgets.
 * Import this once in the app entry point (e.g., main.tsx or providers.tsx).
 */
import { registerWidget } from "@/lib/widget-registry";
import { ScreenerWidget } from "@/components/widgets/screener-widget";
import { WatchlistWidget } from "@/components/widgets/watchlist-widget";
import { ChartWidget } from "@/components/widgets/chart-widget";
import { CommunityFeedWidget } from "@/components/widgets/community-feed-widget";

registerWidget({
  type: "screener",
  title: "Screener",
  icon: "table-2",
  component: ScreenerWidget,
  defaultSettings: { listId: null, columnSetId: null },
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
  defaultSettings: { symbol: null, timeframe: "1D" },
});

registerWidget({
  type: "community_feed",
  title: "Community Feed",
  icon: "message-square",
  component: CommunityFeedWidget,
  defaultSettings: { symbol: null, feed: "general" },
});
