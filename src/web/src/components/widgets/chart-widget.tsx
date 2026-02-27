import { useEffect, useRef } from "react";
import { useWidget } from "@/hooks/use-widget";
import { useLayoutStore } from "@/stores/layout-store";
import type { WidgetProps } from "@/types/layout";
import { TerminalDatafeed } from "@/lib/terminal-datafeed";

const CONTAINER_PREFIX = "tv_chart_";

interface ChartSettings {
  symbol?: string;
  interval?: string;
}

export function ChartWidget({
  instanceId,
  settings,
  onSettingsChange,
}: WidgetProps) {
  const s = (settings ?? {}) as ChartSettings;
  const { channelContext, setChannelSymbol } = useWidget(instanceId);
  const theme = useLayoutStore((s) => s.theme);

  const containerRef = useRef<HTMLDivElement>(null);
  const widgetRef = useRef<IChartingLibraryWidget | null>(null);
  const readyRef = useRef(false);
  const containerId = `${CONTAINER_PREFIX}${instanceId}`;

  // Track the currently loaded symbol to prevent redundant setSymbol calls
  const currentSymbolRef = useRef<string | null>(null);

  // Track latest callbacks in refs for stable closures
  const onSettingsChangeRef = useRef(onSettingsChange);
  onSettingsChangeRef.current = onSettingsChange;
  const setChannelSymbolRef = useRef(setChannelSymbol);
  setChannelSymbolRef.current = setChannelSymbol;

  // Capture the initial symbol once (before the first effect runs)
  const initialSymbolRef = useRef(
    channelContext?.symbol || s.symbol || "NSE:RELIANCE",
  );

  // ─── Initialize TradingView widget (runs once) ─────────────────
  useEffect(() => {
    if (typeof TradingView === "undefined" || !containerRef.current) return;

    const initialSymbol = initialSymbolRef.current;
    currentSymbolRef.current = initialSymbol;

    const isDark = theme === "dark";
    const datafeed = new TerminalDatafeed();
    const tvWidget = new TradingView.widget({
      symbol: initialSymbol,
      interval: "D",
      container: containerId,
      datafeed,
      library_path: "/tv/charting_library/",
      locale: "en",
      autosize: true,
      theme: isDark ? "dark" : "light",
      timezone: "exchange" as any, // Follow symbol metadata (Asia/Kolkata)
      disabled_features: ["study_templates", "header_saveload"],
      enabled_features: ["show_symbol_logos", "show_exchange_logos"],
      loading_screen: {
        backgroundColor: isDark ? "#09090b" : "#fafafa",
        foregroundColor: "#6366f1",
      },
      overrides: {
        "paneProperties.background": isDark ? "#09090b" : "#ffffff",
        "paneProperties.backgroundType": "solid",
      },
    });

    widgetRef.current = tvWidget;

    tvWidget.onChartReady(() => {
      readyRef.current = true;

      // Listen for symbol changes made inside the TradingView search UI
      tvWidget
        .activeChart()
        .onSymbolChanged()
        .subscribe(null, () => {
          const newSymbol = tvWidget.activeChart().symbol();
          if (newSymbol === currentSymbolRef.current) return;
          currentSymbolRef.current = newSymbol;
          onSettingsChangeRef.current({ symbol: newSymbol });
          setChannelSymbolRef.current(newSymbol);
        });
    });

    return () => {
      readyRef.current = false;
      try {
        tvWidget.remove();
      } catch {
        /* already disposed */
      }
      datafeed.destroy(); // Clean up WS session
      widgetRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [containerId]);

  // ─── React to channel symbol changes from other widgets ────────
  const channelSymbol = channelContext?.symbol;
  useEffect(() => {
    if (
      !channelSymbol ||
      channelSymbol === currentSymbolRef.current ||
      !widgetRef.current ||
      !readyRef.current
    )
      return;

    currentSymbolRef.current = channelSymbol;
    widgetRef.current.activeChart().setSymbol(channelSymbol);
    onSettingsChangeRef.current({ symbol: channelSymbol });
  }, [channelSymbol]);

  // ─── Sync TradingView theme with app theme ─────────────────────
  useEffect(() => {
    if (!widgetRef.current || !readyRef.current) return;
    try {
      widgetRef.current.changeTheme(theme === "dark" ? "dark" : "light");
    } catch {
      /* widget may not support changeTheme */
    }
  }, [theme]);

  // ─── Resize handling ───────────────────────────────────────────
  useEffect(() => {
    if (!containerRef.current) return;
    const observer = new ResizeObserver(() => {
      if (widgetRef.current && readyRef.current) {
        try {
          widgetRef.current.resize();
        } catch {
          /* ignore */
        }
      }
    });
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

  return (
    <div ref={containerRef} className="h-full w-full">
      <div id={containerId} className="h-full w-full" />
    </div>
  );
}
