import { useEffect, useRef, useState, useMemo, useCallback } from "react";
import { useWidget } from "@/hooks/use-widget";
import { useLayoutStore } from "@/stores/layout-store";
import type { WidgetProps } from "@/types/layout";
import { TerminalDatafeed } from "@/lib/terminal-datafeed";
import { ChartSession } from "@/lib/chart-session";
import { ChartStorageAdapter } from "@/lib/chart-storage-adapter";
import { getCustomIndicators } from "@/lib/custom-indicators";
import { useAddSymbolMutation, useListsQuery } from "@/queries/use-lists";
import {
  useAlerts,
  useCreateAlert,
  useUpdateAlert,
  useDeleteAlertsByDrawing,
} from "@/queries/use-alerts";
import type { Alert } from "@/types/alert";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { List as ListIcon, X } from "lucide-react";

const CONTAINER_PREFIX = "tv_chart_";
const LAST_SCREENER_LIST_KEY = "last_screener_list_id";

const FLAG_DOT: Record<string, string> = {
  red: "bg-red-500",
  green: "bg-green-500",
  yellow: "bg-yellow-500",
  blue: "bg-blue-500",
  purple: "bg-purple-500",
};

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
  const [chartReady, setChartReady] = useState(false);
  const containerId = `${CONTAINER_PREFIX}${instanceId}`;

  const currentSymbolRef = useRef<string | null>(null);

  const onSettingsChangeRef = useRef(onSettingsChange);
  onSettingsChangeRef.current = onSettingsChange;
  const setChannelSymbolRef = useRef(setChannelSymbol);
  setChannelSymbolRef.current = setChannelSymbol;

  const initialSymbolRef = useRef(
    channelContext?.symbol || s.symbol || "NSE:RELIANCE",
  );

  const addSymbol = useAddSymbolMutation();
  const { data: lists = [] } = useListsQuery();
  const { data: alerts = [] } = useAlerts();
  const createAlert = useCreateAlert();
  const updateAlert = useUpdateAlert();
  const deleteAlertsByDrawing = useDeleteAlertsByDrawing();

  // Stable refs so closures always see latest data
  const listsRef = useRef(lists);
  listsRef.current = lists;
  const addSymbolRef = useRef(addSymbol);
  addSymbolRef.current = addSymbol;
  const alertsRef = useRef(alerts);
  alertsRef.current = alerts;
  const createAlertRef = useRef(createAlert);
  createAlertRef.current = createAlert;
  const updateAlertRef = useRef(updateAlert);
  updateAlertRef.current = updateAlert;
  const deleteAlertsByDrawingRef = useRef(deleteAlertsByDrawing);
  deleteAlertsByDrawingRef.current = deleteAlertsByDrawing;

  // Track order line objects for cleanup
  const alertOrderLinesRef = useRef<Map<string, any>>(new Map());

  // ─── Alert creation from chart context menu ────────────────────
  const handleCreateAlertAtPrice = useCallback(
    (price: number, operator: string) => {
      const symbol = currentSymbolRef.current;
      if (!symbol) return;

      const shortName = symbol.includes(":") ? symbol.split(":")[1] : symbol;
      const opLabel = operator === ">=" ? "≥" : "≤";
      const formulaOp = operator === ">=" ? ">" : "<";

      createAlertRef.current.mutate(
        {
          name: `${shortName} ${opLabel} ${price.toFixed(2)}`,
          symbol,
          alert_type: "formula",
          trigger_condition: { formula: `C ${formulaOp} ${price.toFixed(2)}` },
          frequency: "once",
        },
        {
          onSuccess: () =>
            toast.success(
              `Alert created: ${shortName} ${opLabel} ${price.toFixed(2)}`,
            ),
          onError: () => toast.error("Failed to create alert"),
        },
      );
    },
    [],
  );

  const handleCreateAlertAtPriceRef = useRef(handleCreateAlertAtPrice);
  handleCreateAlertAtPriceRef.current = handleCreateAlertAtPrice;

  // ─── Floating list picker state ────────────────────────────────
  const [listPickerOpen, setListPickerOpen] = useState(false);
  const [pendingSymbol, setPendingSymbol] = useState<string | null>(null);

  const showPickerRef = useRef<(symbol: string) => void>(() => {});
  showPickerRef.current = (symbol: string) => {
    setPendingSymbol(symbol);
    setListPickerOpen(true);
  };

  const pickerLists = useMemo(
    () => lists.filter((l) => l.type === "simple" || l.type === "color"),
    [lists],
  );

  const handleListSelect = (listId: string) => {
    const list = listsRef.current.find((l) => l.id === listId);
    const symbol = pendingSymbol;
    if (!list || !symbol) return;

    setListPickerOpen(false);
    setPendingSymbol(null);
    localStorage.setItem(LAST_SCREENER_LIST_KEY, listId);

    if (list.symbols.includes(symbol)) {
      toast.info(`${symbol} is already in "${list.name}"`);
      return;
    }

    addSymbolRef.current.mutate(
      { listId, ticker: symbol },
      {
        onSuccess: () => toast.success(`Added ${symbol} to "${list.name}"`),
        onError: () => toast.error(`Failed to add ${symbol}`),
      },
    );
  };

  // ─── Initialize TradingView widget (runs once) ─────────────────
  useEffect(() => {
    if (typeof TradingView === "undefined" || !containerRef.current) return;

    const initialSymbol = initialSymbolRef.current;
    currentSymbolRef.current = initialSymbol;

    const isDark = theme === "dark";
    const session = new ChartSession();
    const datafeed = new TerminalDatafeed(session);
    const storageAdapter = new ChartStorageAdapter();

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
      timezone: "exchange" as any,
      load_last_chart: true,
      saved_data: s.chartState ?? undefined,
      save_load_adapter: storageAdapter,
      custom_indicators_getter: getCustomIndicators,
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
      setChartReady(true);

      // ── Context menu: "Alert above / below {price}" ──
      tvWidget.onContextMenu((_unixTime: number, price: number) => {
        return [
          {
            position: "top",
            text: `Alert above ${price.toFixed(2)}`,
            click: () => handleCreateAlertAtPriceRef.current(price, ">="),
          },
          {
            position: "top",
            text: `Alert below ${price.toFixed(2)}`,
            click: () => handleCreateAlertAtPriceRef.current(price, "<="),
          },
        ];
      });

      // ── Drawing ↔ Alert wiring ──────────────────────────────────
      tvWidget.subscribe(
        "drawing_event" as any,
        (drawingId: string, eventType: string) => {
          const chart = tvWidget.activeChart();

          if (eventType === "remove") {
            // Drawing deleted → delete all linked alerts
            const linked = alertsRef.current.filter(
              (a: Alert) => a.drawing_id === drawingId,
            );
            if (linked.length > 0) {
              deleteAlertsByDrawingRef.current.mutate(drawingId, {
                onSuccess: () =>
                  toast.info(
                    `Removed ${linked.length} alert(s) linked to deleted drawing`,
                  ),
              });
            }
            return;
          }

          if (
            eventType === "points_changed" ||
            eventType === "move" ||
            eventType === "properties_changed"
          ) {
            // Drawing moved/resized → update linked alerts
            const linked = alertsRef.current.filter(
              (a: Alert) => a.drawing_id === drawingId,
            );
            if (linked.length === 0) return;

            let shape: any;
            try {
              shape = chart.getShapeById(drawingId as any);
            } catch {
              return;
            }
            if (!shape) return;

            const points = shape.getPoints() as Array<{
              price: number;
              time: number;
            }>;
            if (!points || points.length === 0) return;

            // Determine drawing type from shapes list
            const shapeInfo = chart
              .getAllShapes()
              .find((s: any) => s.id === drawingId);
            const shapeName = shapeInfo?.name || "";

            let triggerCondition: Record<string, unknown> | null = null;

            if (
              shapeName === "horizontal_line" ||
              shapeName === "horizontal_ray"
            ) {
              triggerCondition = {
                drawing_type: "hline",
                trigger_when:
                  (linked[0].trigger_condition as any)?.trigger_when ||
                  "crosses_above",
                price: points[0].price,
              };
            } else if (
              shapeName === "trend_line" ||
              shapeName === "extended" ||
              shapeName === "ray"
            ) {
              triggerCondition = {
                drawing_type: "trendline",
                trigger_when:
                  (linked[0].trigger_condition as any)?.trigger_when ||
                  "crosses_above",
                points: points.slice(0, 2).map((p) => ({
                  time: p.time,
                  price: p.price,
                })),
              };
            } else if (shapeName === "rectangle") {
              if (points.length >= 2) {
                const prices = points.map((p) => p.price);
                const times = points.map((p) => p.time);
                triggerCondition = {
                  drawing_type: "rectangle",
                  trigger_when:
                    (linked[0].trigger_condition as any)?.trigger_when ||
                    "enters",
                  top: Math.max(...prices),
                  bottom: Math.min(...prices),
                  left: Math.min(...times),
                  right: Math.max(...times),
                };
              }
            }

            if (!triggerCondition) return;

            // Update each linked alert with new trigger condition
            for (const alert of linked) {
              updateAlertRef.current.mutate(
                {
                  id: alert.id,
                  data: { trigger_condition: triggerCondition },
                },
                {
                  onSuccess: () =>
                    toast.success(
                      `Alert "${alert.name}" updated with new drawing position`,
                    ),
                },
              );
            }
          }
        },
      );

      // ── Option+W: save current symbol to last-used screener list ──
      tvWidget.onShortcut(["alt", 87], () => {
        const symbol = currentSymbolRef.current;
        if (!symbol) return;

        const listId = localStorage.getItem(LAST_SCREENER_LIST_KEY);
        const list = listId
          ? listsRef.current.find((l) => l.id === listId)
          : null;

        if (!list) {
          showPickerRef.current(symbol);
          return;
        }

        if (list.symbols.includes(symbol)) {
          toast.info(`${symbol} is already in "${list.name}"`);
          return;
        }

        addSymbolRef.current.mutate(
          { listId: list.id, ticker: symbol },
          {
            onSuccess: () => toast.success(`Added ${symbol} to "${list.name}"`),
            onError: () => toast.error(`Failed to add ${symbol}`),
          },
        );
      });

      // Auto-save chart state
      tvWidget.subscribe("onAutoSaveNeeded", () => {
        tvWidget.save((state: object) => {
          onSettingsChangeRef.current({ chartState: state });
        });
      });

      // Sync symbol changes
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

      // Draw alerts whenever the chart has loaded data for the current symbol.
      // Using onDataLoaded imperatively avoids React's async state/effect lag.
      tvWidget
        .activeChart()
        .onDataLoaded()
        .subscribe(null, () => {
          drawAlertsRef.current(tvWidget.activeChart());
        });

      tvWidget
        .activeChart()
        .onIntervalChanged()
        .subscribe(null, (interval: string) => {
          onSettingsChangeRef.current({ interval });
        });
    });

    return () => {
      readyRef.current = false;
      setChartReady(false);
      // Clean up order lines
      alertOrderLinesRef.current.forEach((line) => {
        try {
          line.remove();
        } catch {
          /* already removed */
        }
      });
      alertOrderLinesRef.current.clear();
      try {
        tvWidget.remove();
      } catch {
        /* already disposed */
      }
      session.destroy();
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

  // ─── Sync TradingView theme ────────────────────────────────────
  useEffect(() => {
    if (!widgetRef.current || !readyRef.current) return;
    try {
      widgetRef.current.changeTheme(theme === "dark" ? "dark" : "light");
    } catch {
      /* widget may not support changeTheme */
    }
  }, [theme]);

  // ─── Alert drawing helpers ─────────────────────────────────────
  // Keep a stable ref to the draw function so it can be called
  // imperatively from the onDataLoaded callback without stale closures.
  const drawAlertsRef = useRef<(chart: IChartWidgetApi) => void>(() => {});

  const extractPrice = (alert: Alert): number | null => {
    if (alert.alert_type === "formula") {
      const formula = (alert.trigger_condition as { formula?: string }).formula || "";
      const match = formula.match(/(?:C|CLOSE)\s*[><]=?\s*([\d.]+)/i);
      return match ? parseFloat(match[1]) : null;
    }
    if (alert.alert_type === "drawing") {
      const cond = alert.trigger_condition as Record<string, unknown>;
      if (cond.drawing_type === "hline") return cond.price as number;
    }
    return null;
  };

  // Update the ref whenever alerts change so closures always see current data.
  useEffect(() => {
    drawAlertsRef.current = (chart: IChartWidgetApi) => {
      const currentSymbol = chart.symbol();

      // Remove previously drawn shapes
      alertOrderLinesRef.current.forEach((entityId) => {
        try { chart.removeEntity(entityId as any); } catch { /* already removed */ }
      });
      alertOrderLinesRef.current.clear();

      // Filter active alerts for this symbol
      const matching = alerts.filter((a: Alert) =>
        a.status === "active" &&
        a.symbol.toUpperCase() === currentSymbol.toUpperCase(),
      );

      for (const alert of matching) {
        const price = extractPrice(alert);
        if (price == null) continue;

        const formula = (alert.trigger_condition as { formula?: string }).formula || "";
        const isBelow = /[<]/.test(formula);
        const label = alert.name || `Alert @ ${price.toFixed(2)}`;
        const lineColor = isBelow ? "#EF4444" : "#22C55E";

        chart
          .createShape({ price }, {
            shape: "horizontal_line",
            lock: true,
            disableSelection: true,
            disableSave: true,
            disableUndo: true,
            text: label,
            overrides: {
              linecolor: lineColor,
              linestyle: 2,
              linewidth: 1,
              showLabel: true,
              textcolor: lineColor,
              horzLabelsAlign: "right",
              showPrice: true,
            },
          } as any)
          .then((entityId: any) => {
            if (entityId) alertOrderLinesRef.current.set(alert.id, entityId);
          })
          .catch(() => { /* shape creation may fail */ });
      }
    };
  });

  // ─── Redraw when alerts list changes (add/remove/activate) ──────
  useEffect(() => {
    const tvWidget = widgetRef.current;
    if (!tvWidget || !chartReady) return;
    drawAlertsRef.current(tvWidget.activeChart());
  }, [alerts, chartReady]);


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
    <div ref={containerRef} className="h-full w-full relative">
      <div id={containerId} className="h-full w-full" />

      {/* Floating list picker — shown when Option+W is pressed with no stored list */}
      {listPickerOpen && pendingSymbol && (
        <div
          className="absolute inset-0 z-50 flex items-start justify-center pt-12"
          onClick={() => setListPickerOpen(false)}
        >
          <div
            className="bg-card border border-border rounded-lg shadow-2xl w-64 overflow-hidden animate-in fade-in slide-in-from-top-2 duration-150"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-3 py-2 border-b border-border">
              <div className="flex items-center gap-2">
                <ListIcon className="w-3.5 h-3.5 text-primary" />
                <span className="text-xs font-medium">
                  Add{" "}
                  <span className="text-primary font-mono">
                    {pendingSymbol.includes(":")
                      ? pendingSymbol.split(":")[1]
                      : pendingSymbol}
                  </span>{" "}
                  to list
                </span>
              </div>
              <button
                onClick={() => setListPickerOpen(false)}
                className="text-muted-foreground hover:text-foreground transition-colors"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>

            <div className="py-1 max-h-64 overflow-y-auto">
              {pickerLists.length === 0 ? (
                <div className="px-3 py-4 text-center text-xs text-muted-foreground">
                  No lists available
                </div>
              ) : (
                pickerLists.map((list) => (
                  <button
                    key={list.id}
                    onClick={() => handleListSelect(list.id)}
                    className="w-full flex items-center gap-2 px-3 py-2 text-xs hover:bg-muted/60 transition-colors text-left"
                  >
                    {list.type === "color" && list.color ? (
                      <span
                        className={cn(
                          "w-2 h-2 rounded-full shrink-0",
                          FLAG_DOT[list.color] ?? "bg-muted",
                        )}
                      />
                    ) : (
                      <ListIcon className="w-3 h-3 text-muted-foreground shrink-0" />
                    )}
                    <span className="truncate">{list.name}</span>
                  </button>
                ))
              )}
            </div>

            <div className="px-3 py-1.5 border-t border-border">
              <p className="text-[10px] text-muted-foreground">
                This list will be remembered for future Option+W saves
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
