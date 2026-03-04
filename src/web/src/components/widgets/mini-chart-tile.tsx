import { useEffect, useMemo, useRef, useState } from "react";
import {
  CandlestickSeries,
  ColorType,
  HistogramSeries,
  LineSeries,
  LineStyle,
  PriceScaleMode,
  createChart,
  type IChartApi,
  type IPriceLine,
  type ISeriesApi,
  type Time,
  type UTCTimestamp,
} from "lightweight-charts";
import type { Alert } from "@/types/alert";
import type {
  MiniChartBar,
  MiniChartMAConfig,
  MiniChartScaleMode,
  MiniChartValueItem,
} from "@/types/mini-chart";
import type { MiniChartSession } from "@/lib/mini-chart-session";
import {
  findNearestAlertByY,
  getAlertColor,
  getPriceFromEvent,
  normalizeOperator,
  type UserPriceAlert,
} from "@/lib/lightweight/user-price-alerts";
import { cn } from "@/lib/utils";
import { Trash2 } from "lucide-react";

const DAY_MS = 24 * 60 * 60 * 1000;

interface MiniChartTileProps {
  symbol: string;
  name: string | null | undefined;
  logo: string | null | undefined;
  headerValues: MiniChartValueItem[];
  timeframe: string;
  scaleMode: MiniChartScaleMode;
  maConfigs: MiniChartMAConfig[];
  session: MiniChartSession;
  active: boolean;
  isSelected?: boolean;
  isDark: boolean;
  alerts: Alert[];
  onSelectSymbol: (symbol: string) => void;
  onCreateAlert: (symbol: string, price: number, operator: string) => void;
  onModifyAlert: (alert: Alert, price: number) => void;
  onDeleteAlert: (alert: Alert) => void;
}

interface ContextMenuState {
  open: boolean;
  x: number;
  y: number;
  price: number | null;
  nearestAlertId: string | null;
}

function toChartTime(ms: number): UTCTimestamp {
  return Math.floor(ms / 1000) as UTCTimestamp;
}

function mergeBar(prev: MiniChartBar[], next: MiniChartBar): MiniChartBar[] {
  if (prev.length === 0) return [next];
  const last = prev[prev.length - 1];
  if (next.time === last.time) {
    return [...prev.slice(0, -1), next];
  }
  if (next.time > last.time) {
    return [...prev, next];
  }

  const idx = prev.findIndex((b) => b.time === next.time);
  if (idx === -1) {
    return prev;
  }

  const out = [...prev];
  out[idx] = next;
  return out;
}

function computeEMA(bars: MiniChartBar[], length: number): Array<{ time: Time; value: number }> {
  if (length <= 1 || bars.length < length) return [];

  const k = 2 / (length + 1);
  let ema = 0;
  const out: Array<{ time: Time; value: number }> = [];

  for (let i = 0; i < bars.length; i++) {
    const close = bars[i].close;
    if (i < length - 1) continue;

    if (i === length - 1) {
      const seed = bars.slice(0, length).reduce((acc, b) => acc + b.close, 0) / length;
      ema = seed;
      out.push({ time: toChartTime(bars[i].time), value: ema });
      continue;
    }

    ema = close * k + ema * (1 - k);
    out.push({ time: toChartTime(bars[i].time), value: ema });
  }

  return out;
}

function formatHeaderValue(value: unknown): string {
  if (value == null) return "-";
  if (typeof value === "number") {
    if (!Number.isFinite(value)) return "-";
    return value.toLocaleString("en-US", { maximumFractionDigits: 2 });
  }
  if (typeof value === "boolean") return value ? "Yes" : "No";
  return String(value);
}

function shortSymbol(symbol: string): string {
  const idx = symbol.lastIndexOf(":");
  return idx >= 0 ? symbol.slice(idx + 1) : symbol;
}

function timeToMs(time: Time | null | undefined): number | null {
  if (time == null) return null;
  if (typeof time === "number") return Number(time) * 1000;
  if (typeof time === "string") {
    const parsed = Date.parse(time);
    return Number.isNaN(parsed) ? null : parsed;
  }
  if (
    typeof time === "object" &&
    "year" in time &&
    "month" in time &&
    "day" in time
  ) {
    return Date.UTC(time.year, time.month - 1, time.day);
  }
  return null;
}

export function MiniChartTile({
  symbol,
  name,
  logo,
  headerValues,
  timeframe,
  scaleMode,
  maConfigs,
  session,
  active,
  isSelected = false,
  isDark,
  alerts,
  onSelectSymbol,
  onCreateAlert,
  onModifyAlert,
  onDeleteAlert,
}: MiniChartTileProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const maSeriesRef = useRef<Map<string, ISeriesApi<"Line">>>(new Map());
  const alertLineRef = useRef<Map<string, IPriceLine>>(new Map());
  const hasFittedRef = useRef(false);
  const backfillInFlightRef = useRef(false);
  const noMoreHistoryRef = useRef(false);

  const [bars, setBars] = useState<MiniChartBar[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [alertOverrides, setAlertOverrides] = useState<Record<string, number>>({});
  const [draggingAlertId, setDraggingAlertId] = useState<string | null>(null);
  const [menu, setMenu] = useState<ContextMenuState>({
    open: false,
    x: 0,
    y: 0,
    price: null,
    nearestAlertId: null,
  });

  const effectiveAlerts = useMemo(() => {
    return alerts
      .filter((alert) => alert.status === "enabled")
      .filter((alert) => alert.rhs_type === "constant" && alert.rhs_constant != null)
      .map((alert) => {
        const price = alertOverrides[alert.uuid] ?? alert.rhs_constant ?? 0;
        const op = normalizeOperator(alert.operator);
        const label = alert.name || `${shortSymbol(symbol)} ${op} ${price.toFixed(2)}`;
        return {
          id: alert.uuid,
          price,
          operator: op,
          label,
          color: getAlertColor(op),
        } as UserPriceAlert;
      });
  }, [alerts, alertOverrides, symbol]);

  const selectedAlert = useMemo(
    () =>
      menu.nearestAlertId
        ? alerts.find((a) => a.uuid === menu.nearestAlertId) ?? null
        : null,
    [alerts, menu.nearestAlertId],
  );

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const chart = createChart(container, {
      autoSize: true,
      layout: {
        background: {
          type: ColorType.Solid,
          color: isDark ? "#0A0B0F" : "#FFFFFF",
        },
        textColor: isDark ? "#C7CDD6" : "#1F2937",
        fontFamily: getComputedStyle(document.body).fontFamily,
      },
      grid: {
        vertLines: { visible: false, color: "transparent" },
        horzLines: { visible: false, color: "transparent" },
      },
      rightPriceScale: {
        borderVisible: false,
        minimumWidth: 72,
        entireTextOnly: true,
      },
      timeScale: {
        borderVisible: false,
        rightOffset: 8,
      },
      handleScale: {
        axisPressedMouseMove: true,
        mouseWheel: true,
        pinch: true,
      },
      handleScroll: {
        mouseWheel: false,
        pressedMouseMove: true,
        vertTouchDrag: true,
        horzTouchDrag: true,
      },
      crosshair: {
        vertLine: { visible: false },
      },
    });

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: "#2563EB",
      downColor: "#EC4899",
      borderVisible: false,
      wickUpColor: "#2563EB",
      wickDownColor: "#EC4899",
      priceLineVisible: false,
      lastValueVisible: true,
    });

    const volumeSeries = chart.addSeries(HistogramSeries, {
      priceFormat: { type: "volume" },
      priceScaleId: "",
      lastValueVisible: false,
      priceLineVisible: false,
    });

    chart.priceScale("").applyOptions({
      scaleMargins: {
        top: 0.78,
        bottom: 0,
      },
    });

    chartRef.current = chart;
    candleSeriesRef.current = candleSeries;
    volumeSeriesRef.current = volumeSeries;

    const alertLines = alertLineRef.current;
    const maSeriesMap = maSeriesRef.current;

    return () => {
      alertLines.forEach((line) => {
        try {
          candleSeries.removePriceLine(line);
        } catch {
          // no-op
        }
      });
      alertLines.clear();

      maSeriesMap.forEach((series) => {
        try {
          chart.removeSeries(series);
        } catch {
          // no-op
        }
      });
      maSeriesMap.clear();

      chart.remove();
      chartRef.current = null;
      candleSeriesRef.current = null;
      volumeSeriesRef.current = null;
    };
  }, [isDark]);

  useEffect(() => {
    if (!chartRef.current) return;

    chartRef.current.priceScale("right").applyOptions({
      mode:
        scaleMode === "log"
          ? PriceScaleMode.Logarithmic
          : PriceScaleMode.Normal,
    });
  }, [scaleMode]);

  useEffect(() => {
    let mounted = true;

    // Defer state reset to avoid synchronous setState-in-effect lint noise,
    // but keep ordering before the load promise handlers.
    queueMicrotask(() => {
      if (!mounted) return;
      hasFittedRef.current = false;
      backfillInFlightRef.current = false;
      noMoreHistoryRef.current = false;
      setLoading(true);
      setLoadError(null);
    });

    const load = (attempt: number) => {
      session
        .loadHistory(symbol, timeframe)
        .then((history) => {
          if (!mounted) return;
          setBars(history);
          setLoading(false);
        })
        .catch((err: Error) => {
          if (!mounted) return;
          const msg = err.message || "Failed to load chart";
          if (attempt < 2 && msg.toLowerCase().includes("timeout")) {
            setTimeout(() => load(attempt + 1), 400);
            return;
          }
          setLoadError(msg);
          setLoading(false);
        });
    };

    load(1);

    return () => {
      mounted = false;
    };
  }, [session, symbol, timeframe]);

  useEffect(() => {
    if (!active) return;

    return session.subscribe(symbol, timeframe, (bar) => {
      setBars((prev) => mergeBar(prev, bar));
    });
  }, [active, session, symbol, timeframe]);

  useEffect(() => {
    const candleSeries = candleSeriesRef.current;
    const volumeSeries = volumeSeriesRef.current;
    if (!candleSeries || !volumeSeries) return;

    candleSeries.setData(
      bars.map((bar) => ({
        time: toChartTime(bar.time),
        open: bar.open,
        high: bar.high,
        low: bar.low,
        close: bar.close,
      })),
    );

    volumeSeries.setData(
      bars.map((bar) => ({
        time: toChartTime(bar.time),
        value: bar.volume,
        color: bar.close >= bar.open ? "#60A5FA88" : "#F472B688",
      })),
    );

    const maMap = maSeriesRef.current;
    const chart = chartRef.current;
    if (!chart) return;

    const enabledIds = new Set(maConfigs.filter((m) => m.enabled).map((m) => m.id));

    maMap.forEach((series, id) => {
      if (!enabledIds.has(id)) {
        try {
          chart.removeSeries(series);
        } catch {
          // no-op
        }
        maMap.delete(id);
      }
    });

    for (const ma of maConfigs) {
      if (!ma.enabled) continue;

      let series = maMap.get(ma.id);
      if (!series) {
        series = chart.addSeries(LineSeries, {
          color: ma.color,
          lineWidth: 2,
          priceLineVisible: false,
          lastValueVisible: false,
        });
        maMap.set(ma.id, series);
      } else {
        series.applyOptions({ color: ma.color, lineWidth: 2 });
      }

      series.setData(computeEMA(bars, ma.length));
    }

    if (!hasFittedRef.current && bars.length > 0) {
      chart.timeScale().fitContent();
      hasFittedRef.current = true;
    }
  }, [bars, maConfigs]);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart || !active || loading || bars.length === 0) return;

    let cancelled = false;

    const onVisibleRangeChange = (range: { from: Time; to: Time } | null) => {
      if (cancelled || !range) return;
      if (backfillInFlightRef.current || noMoreHistoryRef.current) return;

      const fromMs = timeToMs(range.from);
      if (fromMs == null) return;

      const earliestLoaded = bars[0].time;
      const triggerThresholdMs = earliestLoaded + 7 * DAY_MS;
      if (fromMs > triggerThresholdMs) return;

      backfillInFlightRef.current = true;
      session
        .loadHistoryBefore(symbol, timeframe, earliestLoaded)
        .then((merged) => {
          if (cancelled) return;
          if (merged.length === 0) {
            noMoreHistoryRef.current = true;
            return;
          }

          const nextEarliest = merged[0]?.time ?? earliestLoaded;
          if (nextEarliest >= earliestLoaded) {
            noMoreHistoryRef.current = true;
            return;
          }

          setBars(merged);
        })
        .catch(() => {
          // no-op
        })
        .finally(() => {
          backfillInFlightRef.current = false;
        });
    };

    const timeScale = chart.timeScale();
    timeScale.subscribeVisibleTimeRangeChange(onVisibleRangeChange);
    return () => {
      cancelled = true;
      timeScale.unsubscribeVisibleTimeRangeChange(onVisibleRangeChange);
    };
  }, [active, bars, loading, session, symbol, timeframe]);

  useEffect(() => {
    const candleSeries = candleSeriesRef.current;
    if (!candleSeries) return;

    const existing = alertLineRef.current;
    const incoming = new Set(effectiveAlerts.map((a) => a.id));

    existing.forEach((line, id) => {
      if (!incoming.has(id)) {
        try {
          candleSeries.removePriceLine(line);
        } catch {
          // no-op
        }
        existing.delete(id);
      }
    });

    for (const alert of effectiveAlerts) {
      const line = existing.get(alert.id);
      if (!line) {
        const created = candleSeries.createPriceLine({
          price: alert.price,
          color: alert.color,
          lineWidth: 1,
          lineStyle: LineStyle.Dotted,
          axisLabelVisible: true,
          title: alert.label,
        });
        existing.set(alert.id, created);
      } else {
        line.applyOptions({
          price: alert.price,
          color: alert.color,
          title: alert.label,
        });
      }
    }
  }, [effectiveAlerts]);

  useEffect(() => {
    if (!menu.open) return;

    const onWindowClick = () => {
      setMenu((prev) => ({ ...prev, open: false }));
    };

    window.addEventListener("click", onWindowClick);
    return () => window.removeEventListener("click", onWindowClick);
  }, [menu.open]);

  const handleContextMenu = (e: React.MouseEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();

    const container = containerRef.current;
    const candleSeries = candleSeriesRef.current;
    if (!container || !candleSeries) return;

    const rect = container.getBoundingClientRect();
    const y = e.clientY - rect.top;

    const price = getPriceFromEvent(container, e.clientY, (coord) =>
      candleSeries.coordinateToPrice(coord),
    );

    const nearest = findNearestAlertByY(
      effectiveAlerts,
      y,
      (p) => candleSeries.priceToCoordinate(p),
      8,
    );

    setMenu({
      open: true,
      x: e.clientX - rect.left,
      y,
      price,
      nearestAlertId: nearest?.alert.id ?? null,
    });
  };

  const handlePointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    if (e.button !== 0) return;

    const container = containerRef.current;
    const candleSeries = candleSeriesRef.current;
    if (!container || !candleSeries) return;

    const rect = container.getBoundingClientRect();
    const y = e.clientY - rect.top;

    const nearest = findNearestAlertByY(
      effectiveAlerts,
      y,
      (p) => candleSeries.priceToCoordinate(p),
      7,
    );

    if (!nearest) return;

    e.preventDefault();
    setDraggingAlertId(nearest.alert.id);
    container.setPointerCapture(e.pointerId);
  };

  const handlePointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!draggingAlertId) return;

    const container = containerRef.current;
    const candleSeries = candleSeriesRef.current;
    if (!container || !candleSeries) return;

    const price = getPriceFromEvent(container, e.clientY, (coord) =>
      candleSeries.coordinateToPrice(coord),
    );

    if (price == null) return;

    setAlertOverrides((prev) => ({
      ...prev,
      [draggingAlertId]: Number(price.toFixed(2)),
    }));
  };

  const handlePointerUp = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!draggingAlertId) return;

    const alert = alerts.find((a) => a.uuid === draggingAlertId);
    const nextPrice = alertOverrides[draggingAlertId];

    if (alert && nextPrice != null && Math.abs((alert.rhs_constant ?? 0) - nextPrice) > 0.0001) {
      onModifyAlert(alert, nextPrice);
    }

    setDraggingAlertId(null);

    const container = containerRef.current;
    if (container && container.hasPointerCapture(e.pointerId)) {
      container.releasePointerCapture(e.pointerId);
    }
  };

  return (
    <div
      className={cn(
        "relative h-full w-full rounded-sm border border-border/70 bg-card/90 overflow-hidden",
        isSelected && "border-primary/70 ring-1 ring-primary/30",
        draggingAlertId && "cursor-ns-resize",
      )}
      onContextMenu={handleContextMenu}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
    >
      <div className="absolute left-0 right-0 top-0 z-20 bg-background/90 backdrop-blur pl-2 pr-4 py-1 border-b border-border/60">
        <div className="flex items-center gap-2 min-w-0">
          {logo ? (
            <img
              src={`https://s3-symbol-logo.tradingview.com/${logo}.svg`}
              alt=""
              className="size-3.5 rounded-full bg-muted shrink-0"
            />
          ) : (
            <div className="size-3.5 rounded-full bg-primary/20 text-[8px] text-primary flex items-center justify-center shrink-0">
              {shortSymbol(symbol).slice(0, 1)}
            </div>
          )}
          <button
            className="min-w-0 text-left shrink-0 max-w-[34%]"
            onClick={(e) => {
              e.stopPropagation();
              onSelectSymbol(symbol);
            }}
            title={symbol}
          >
            <p
              className={cn(
                "text-[11px] font-semibold truncate leading-4",
                isSelected ? "text-primary" : "text-foreground",
              )}
            >
              {shortSymbol(symbol)}
            </p>
            <p className="text-[10px] text-muted-foreground truncate leading-4">
              {name ?? symbol}
            </p>
          </button>
          <div className="ml-auto flex items-start justify-end gap-2 min-w-0 flex-1 pr-1">
            {headerValues.slice(0, 4).map((item) => (
              <div key={item.colId} className="min-w-0 max-w-[68px] text-right">
                <p className="text-[8px] uppercase text-muted-foreground truncate leading-3">
                  {item.name}
                </p>
                <p className="text-[10px] text-foreground truncate leading-3.5 tabular-nums">
                  {formatHeaderValue(item.value)}
                </p>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div ref={containerRef} className="absolute inset-0 pt-[56px] pr-4" />

      {loading && (
        <div className="absolute inset-0 z-30 flex items-center justify-center text-xs text-muted-foreground bg-background/50">
          Loading...
        </div>
      )}

      {!loading && loadError && (
        <div className="absolute inset-0 z-30 flex items-center justify-center text-xs text-destructive bg-background/70 px-3 text-center">
          {loadError}
        </div>
      )}

      {menu.open && (
        <div
          className="absolute z-40 min-w-44 rounded-sm border border-border bg-popover shadow-lg py-1"
          style={{ left: Math.max(4, menu.x), top: Math.max(58, menu.y) }}
          onClick={(e) => e.stopPropagation()}
        >
          <button
            className="w-full px-2 py-1 text-left text-xs hover:bg-muted"
            disabled={menu.price == null}
            onClick={() => {
              if (menu.price != null) {
                onCreateAlert(symbol, menu.price, ">=");
              }
              setMenu((prev) => ({ ...prev, open: false }));
            }}
          >
            Alert above {menu.price != null ? menu.price.toFixed(2) : "-"}
          </button>
          <button
            className="w-full px-2 py-1 text-left text-xs hover:bg-muted"
            disabled={menu.price == null}
            onClick={() => {
              if (menu.price != null) {
                onCreateAlert(symbol, menu.price, "<=");
              }
              setMenu((prev) => ({ ...prev, open: false }));
            }}
          >
            Alert below {menu.price != null ? menu.price.toFixed(2) : "-"}
          </button>

          {selectedAlert && (
            <button
              className="w-full px-2 py-1 text-left text-xs text-destructive hover:bg-muted inline-flex items-center gap-1"
              onClick={() => {
                onDeleteAlert(selectedAlert);
                setMenu((prev) => ({ ...prev, open: false }));
              }}
            >
              <Trash2 className="size-3" />
              Delete alert
            </button>
          )}
        </div>
      )}
    </div>
  );
}
