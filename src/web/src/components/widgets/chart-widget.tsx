import { useEffect, useRef } from "react";
import { useWidget } from "@/hooks/use-widget";
import { useLayoutStore } from "@/stores/layout-store";
import type { WidgetProps } from "@/types/layout";
import { TerminalDatafeed } from "@/lib/terminal-datafeed";
import { ChartStorageAdapter } from "@/lib/chart-storage-adapter";

const CONTAINER_PREFIX = "tv_chart_";

interface ChartSettings {
  symbol?: string;
  interval?: string;
  chartState?: object | null;
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
    const storageAdapter = new ChartStorageAdapter();

    // Fire-and-forget hydration from server — doesn't block chart load
    storageAdapter.hydrate();

    const tvWidget = new TradingView.widget({
      symbol: initialSymbol,
      interval: (s.interval ?? "D") as any,
      container: containerId,
      datafeed,
      library_path: "/tv/charting_library/",
      locale: "en",
      autosize: true,
      theme: isDark ? "dark" : "light",
      timezone: "exchange" as any, // Follow symbol metadata (Asia/Kolkata)
      load_last_chart: true,
      saved_data: s.chartState ?? undefined,
      save_load_adapter: storageAdapter,
      enabled_features: [
        "show_symbol_logos",
        "show_exchange_logos",
        "use_localstorage_for_settings",
        "save_chart_properties_to_local_storage",
      ],
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

      // Auto-save chart state (drawings + studies) whenever TV requests it
      tvWidget.subscribe("onAutoSaveNeeded", () => {
        tvWidget.save((state: object) => {
          onSettingsChangeRef.current({ chartState: state });
        });
      });

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

      // Persist interval changes
      tvWidget
        .activeChart()
        .onIntervalChanged()
        .subscribe(null, (interval: string) => {
          onSettingsChangeRef.current({ interval });
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
