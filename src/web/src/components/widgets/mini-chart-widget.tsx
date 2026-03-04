import { useEffect, useMemo, useRef, useState } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { List as ListIcon, Plus, SlidersHorizontal, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { useWidget } from "@/hooks/use-widget";
import { useScreener } from "@/hooks/use-screener";
import { useLayoutStore } from "@/stores/layout-store";
import {
  useListsQuery,
  useRemoveSymbolMutation,
  useSetFlagMutation,
} from "@/queries/use-lists";
import {
  useAlertsQuery,
  useCreateAlertMutation,
  useDeleteAlertMutation,
  useModifyAlertMutation,
} from "@/queries/use-alerts";
import { useBrokers } from "@/hooks/use-brokers";
import { DEFAULT_SCREENER_COLUMNS } from "@/lib/register-widgets";
import { MiniChartTile } from "@/components/widgets/mini-chart-tile";
import { ListSelectionDialog } from "@/components/widgets/list-selection-dialog";
import { MiniChartSession } from "@/lib/mini-chart-session";
import type { Alert } from "@/types/alert";
import type { WidgetProps } from "@/types/layout";
import type { ColumnDef, FilterState } from "@/types/models";
import type {
  MiniChartMAType,
  MiniChartSettings,
  MiniChartSortDirection,
  MiniChartValueItem,
  MiniChartMAConfig,
} from "@/types/mini-chart";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

interface DisplayRow {
  rowIndex: number;
  ticker: string;
  name: string | null | undefined;
  logo: string | null | undefined;
}

const TIMEFRAME_OPTIONS = ["1", "5", "15", "60", "1D", "1W", "1M"];
const GRID_OPTIONS = [2, 3, 4, 5];
const GRID_ROW_HEIGHT = 320;

function inferMarketFromSymbol(symbol: string): "india" | "us" {
  const exchange = symbol.includes(":") ? symbol.split(":")[0].toUpperCase() : "";
  if (exchange === "NSE" || exchange === "BSE") return "india";
  return "us";
}

function sanitizeColumns(columns: ColumnDef[]): ColumnDef[] {
  return columns.map((col) => ({
    ...col,
    filter: "off" as FilterState,
  }));
}

function clampGridColumns(value: number): number {
  return Math.max(2, Math.min(5, value));
}

function createMAConfig(maType: MiniChartMAType): MiniChartMAConfig {
  const suffix =
    typeof crypto !== "undefined" && crypto.randomUUID
      ? crypto.randomUUID().slice(0, 8)
      : Math.random().toString(36).slice(2, 10);
  return {
    id: `${maType}-${suffix}`,
    maType,
    length: maType === "ema" ? 20 : 50,
    color: maType === "ema" ? "#3B82F6" : "#F59E0B",
    enabled: true,
  };
}

function defaultMiniChartSettings(): MiniChartSettings {
  const columns = sanitizeColumns(DEFAULT_SCREENER_COLUMNS);
  return {
    listId: null,
    viewMode: "grid",
    columns,
    headerColumnIds: columns.slice(0, 3).map((col) => col.id),
    sortKey: "ticker",
    sortDirection: "asc",
    timeframe: "1D",
    scaleMode: "linear",
    maConfigs: [
      { id: "ema20", maType: "ema", length: 20, color: "#3B82F6", enabled: true },
      { id: "sma50", maType: "sma", length: 50, color: "#EC4899", enabled: false },
    ],
    gridColumns: 3,
  };
}

function sortDisplayRows(
  rows: DisplayRow[],
  sortKey: string,
  sortDirection: MiniChartSortDirection,
  values: Record<string, unknown[]>,
): DisplayRow[] {
  const multiplier = sortDirection === "asc" ? 1 : -1;

  return [...rows].sort((a, b) => {
    let left: unknown;
    let right: unknown;

    if (sortKey === "ticker") {
      left = a.ticker;
      right = b.ticker;
    } else {
      left = values[sortKey]?.[a.rowIndex];
      right = values[sortKey]?.[b.rowIndex];
    }

    if (left == null && right == null) return a.ticker.localeCompare(b.ticker);
    if (left == null) return 1;
    if (right == null) return -1;

    if (typeof left === "string" && typeof right === "string") {
      const cmp = left.localeCompare(right);
      if (cmp !== 0) return cmp * multiplier;
      return a.ticker.localeCompare(b.ticker);
    }

    if (typeof left === "number" && typeof right === "number") {
      if (left === right) return a.ticker.localeCompare(b.ticker);
      return (left < right ? -1 : 1) * multiplier;
    }

    const cmp = String(left).localeCompare(String(right));
    if (cmp !== 0) return cmp * multiplier;
    return a.ticker.localeCompare(b.ticker);
  });
}

export function MiniChartWidget({ instanceId, settings, onSettingsChange }: WidgetProps) {
  const { setChannelSymbol, channelContext } = useWidget(instanceId);
  const { data: lists = [] } = useListsQuery();
  const { data: allAlerts = [] } = useAlertsQuery();
  const createAlert = useCreateAlertMutation();
  const modifyAlert = useModifyAlertMutation();
  const deleteAlert = useDeleteAlertMutation();
  const setFlagMutation = useSetFlagMutation();
  const removeSymbolMutation = useRemoveSymbolMutation();
  const { data: brokers = [], defaults, openLogin } = useBrokers();

  const theme = useLayoutStore((s) => s.theme);
  const isDark = theme === "dark";

  const [listDialogOpen, setListDialogOpen] = useState(false);
  const sessionRef = useRef<MiniChartSession | null>(null);
  const [sessionReady, setSessionReady] = useState(false);

  useEffect(() => {
    const session = new MiniChartSession();
    sessionRef.current = session;
    setSessionReady(true);

    return () => {
      session.destroy();
      sessionRef.current = null;
      setSessionReady(false);
    };
  }, []);

  const defaultsMerged = useMemo(() => {
    const incoming = (settings ?? {}) as Partial<MiniChartSettings>;
    const base = defaultMiniChartSettings();
    const merged: MiniChartSettings = {
      ...base,
      ...incoming,
      viewMode: "grid",
      columns: incoming.columns ? sanitizeColumns(incoming.columns) : base.columns,
      headerColumnIds:
        incoming.headerColumnIds?.slice(0, 4) ?? base.headerColumnIds,
      maConfigs: (incoming.maConfigs ?? base.maConfigs).map((ma) => ({
        ...ma,
        maType: (ma as MiniChartMAConfig).maType ?? "ema",
        length: Math.max(2, Math.floor(ma.length || 20)),
      })),
      gridColumns: clampGridColumns(incoming.gridColumns ?? base.gridColumns),
    };

    if (!merged.columns.find((col) => col.id === merged.sortKey) && merged.sortKey !== "ticker") {
      merged.sortKey = "ticker";
    }

    return merged;
  }, [settings]);

  const effectiveListId =
    defaultsMerged.listId ?? lists.find((l) => l.type !== "color")?.id ?? null;

  const selectedList = useMemo(
    () => lists.find((l) => l.id === effectiveListId) ?? null,
    [lists, effectiveListId],
  );

  const screenerColumns = defaultsMerged.columns;

  const { tickers, values, isLoading } = useScreener(
    instanceId,
    effectiveListId,
    effectiveListId ? screenerColumns : null,
    false,
  );

  const displayRows = useMemo<DisplayRow[]>(() => {
    const rows: DisplayRow[] = [];
    for (let i = 0; i < tickers.length; i++) {
      const row = tickers[i];
      if (row.ticker.startsWith("###")) continue;
      rows.push({
        rowIndex: i,
        ticker: row.ticker,
        name: row.name,
        logo: row.logo,
      });
    }

    return sortDisplayRows(rows, defaultsMerged.sortKey, defaultsMerged.sortDirection, values);
  }, [tickers, values, defaultsMerged.sortKey, defaultsMerged.sortDirection]);

  const sortColumns = useMemo(() => {
    return [
      { id: "ticker", name: "Ticker" },
      ...screenerColumns.map((col) => ({ id: col.id, name: col.name })),
    ];
  }, [screenerColumns]);

  const alertMap = useMemo(() => {
    const map = new Map<string, Alert[]>();

    for (const alert of allAlerts) {
      const key = `${alert.lhs_exchange}:${alert.lhs_tradingsymbol}`.toUpperCase();
      const existing = map.get(key);
      if (existing) {
        existing.push(alert);
      } else {
        map.set(key, [alert]);
      }
    }

    return map;
  }, [allAlerts]);

  const colorLists = useMemo(
    () => lists.filter((l) => l.type === "color"),
    [lists],
  );

  const findColorListForSymbol = (symbol: string) => {
    return colorLists.find((l) => l.symbols.includes(symbol)) ?? null;
  };

  const getFlagColor = (symbol: string): string | null => {
    return findColorListForSymbol(symbol)?.color ?? null;
  };

  const handleToggleFlag = (symbol: string, currentColor: string | null) => {
    const currentList = findColorListForSymbol(symbol);
    if (currentColor && currentList) {
      removeSymbolMutation.mutate({ listId: currentList.id, ticker: symbol });
      return;
    }

    const lastUsedColor = localStorage.getItem("last_flag_color") || "red";
    const targetList =
      colorLists.find((l) => l.color === lastUsedColor) ?? colorLists[0] ?? null;
    if (!targetList) return;
    setFlagMutation.mutate({ targetListId: targetList.id, ticker: symbol });
  };

  const handleSelectFlagColor = (
    symbol: string,
    color: string,
    currentColor: string | null,
  ) => {
    const currentList = findColorListForSymbol(symbol);
    if (currentColor === color && currentList) {
      removeSymbolMutation.mutate({ listId: currentList.id, ticker: symbol });
      return;
    }

    localStorage.setItem("last_flag_color", color);
    const targetList = colorLists.find((l) => l.color === color);
    if (!targetList) return;
    setFlagMutation.mutate({ targetListId: targetList.id, ticker: symbol });
  };

  const scrollRef = useRef<HTMLDivElement | null>(null);
  const [gridRowHeight, setGridRowHeight] = useState(GRID_ROW_HEIGHT);

  useEffect(() => {
    const container = scrollRef.current;
    if (!container) return;

    const update = () => {
      const next = Math.max(180, Math.floor((container.clientHeight - 8) / 2));
      setGridRowHeight(next);
    };

    update();
    const observer = new ResizeObserver(update);
    observer.observe(container);
    return () => observer.disconnect();
  }, []);

  const rowCount = Math.ceil(displayRows.length / defaultsMerged.gridColumns);

  const rowVirtualizer = useVirtualizer({
    count: rowCount,
    getScrollElement: () => scrollRef.current,
    estimateSize: () => gridRowHeight,
    overscan: 3,
  });

  useEffect(() => {
    rowVirtualizer.measure();
  }, [gridRowHeight, rowVirtualizer, defaultsMerged.gridColumns]);

  const resolveProvider = async (
    symbol: string,
  ): Promise<{ providerId: string; market: "india" | "us" } | null> => {
    const market = inferMarketFromSymbol(symbol);

    const connected = brokers.filter(
      (broker) =>
        broker.connected &&
        broker.capabilities.includes("alerts") &&
        broker.markets.includes(market),
    );

    const defaultProviderId =
      defaults.find((item) => item.capability === "alerts" && item.market === market)
        ?.provider_id ?? null;

    if (defaultProviderId) {
      const preferred = connected.find((broker) => broker.provider_id === defaultProviderId);
      if (preferred) {
        return { providerId: preferred.provider_id, market };
      }
    }

    if (connected.length > 0) {
      return { providerId: connected[0].provider_id, market };
    }

    const anyConnected = brokers.find(
      (broker) => broker.connected && broker.capabilities.includes("alerts"),
    );

    if (anyConnected) {
      return { providerId: anyConnected.provider_id, market };
    }

    const loginTarget =
      brokers.find(
        (broker) =>
          broker.capabilities.includes("alerts") && broker.markets.includes(market),
      ) ?? brokers.find((broker) => broker.capabilities.includes("alerts"));

    if (loginTarget) {
      await openLogin(loginTarget.provider_id);
      toast.info("Connect your broker account to create alerts.");
    } else {
      toast.error("No alert-capable broker is configured.");
    }

    return null;
  };

  const handleCreateAlert = (symbol: string, price: number, operator: string) => {
    resolveProvider(symbol)
      .then((resolved) => {
        if (!resolved) return;

        const [exchange, tradingsymbol] = symbol.includes(":")
          ? symbol.split(":")
          : ["NSE", symbol];

        const op = operator === "<" ? "<=" : operator === ">" ? ">=" : operator;
        const opLabel = op === ">=" ? "≥" : op;

        createAlert.mutate(
          {
            provider_id: resolved.providerId,
            name: `${tradingsymbol} ${opLabel} ${price.toFixed(2)}`,
            lhs_exchange: exchange,
            lhs_tradingsymbol: tradingsymbol,
            lhs_attribute: "LastTradedPrice",
            operator: op,
            rhs_type: "constant",
            rhs_constant: Number(price.toFixed(2)),
            type: "simple",
          },
          {
            onSuccess: () => toast.success("Alert created"),
            onError: () => toast.error("Failed to create alert"),
          },
        );
      })
      .catch(() => {
        toast.error("Failed to resolve alert provider");
      });
  };

  const handleModifyAlert = (alert: Alert, price: number) => {
    modifyAlert.mutate(
      {
        id: alert.uuid,
        provider_id: alert.provider_id,
        rhs_constant: Number(price.toFixed(2)),
      },
      {
        onError: () => toast.error("Failed to update alert"),
      },
    );
  };

  const handleDeleteAlert = (alert: Alert) => {
    deleteAlert.mutate(
      {
        provider_id: alert.provider_id,
        uuids: [alert.uuid],
      },
      {
        onError: () => toast.error("Failed to delete alert"),
      },
    );
  };

  const handleHeaderToggle = (colId: string) => {
    const current = defaultsMerged.headerColumnIds;

    if (current.includes(colId)) {
      onSettingsChange({
        headerColumnIds: current.filter((id) => id !== colId),
      });
      return;
    }

    if (current.length >= 4) {
      toast.info("You can show up to 4 header values.");
      return;
    }

    onSettingsChange({
      headerColumnIds: [...current, colId],
    });
  };

  const updateMA = (maId: string, patch: Partial<MiniChartMAConfig>) => {
    const updated = defaultsMerged.maConfigs.map((ma) =>
      ma.id === maId
        ? {
            ...ma,
            ...patch,
            length:
              patch.length != null
                ? Math.max(2, Math.floor(patch.length))
                : ma.length,
          }
        : ma,
    );
    onSettingsChange({ maConfigs: updated });
  };

  const updateMAType = (maId: string, maType: MiniChartMAType) => {
    updateMA(maId, { maType });
  };

  const addMA = (maType: MiniChartMAType) => {
    onSettingsChange({ maConfigs: [...defaultsMerged.maConfigs, createMAConfig(maType)] });
  };

  const removeMA = (maId: string) => {
    onSettingsChange({ maConfigs: defaultsMerged.maConfigs.filter((ma) => ma.id !== maId) });
  };

  const getHeaderValues = (row: DisplayRow): MiniChartValueItem[] => {
    return defaultsMerged.headerColumnIds.slice(0, 4).map((colId) => {
      const col = screenerColumns.find((c) => c.id === colId);
      return {
        colId,
        name: col?.name ?? colId,
        value: values[colId]?.[row.rowIndex],
      };
    });
  };

  const activeSymbol = (channelContext?.symbol ?? "").toUpperCase();

  const session = sessionRef.current;

  return (
    <div className="flex h-full flex-col bg-background">
      <div className="flex items-center gap-2 p-2 border-b border-border shrink-0">
        <button
          className="inline-flex items-center gap-2 h-7 rounded-sm border border-border px-2 text-xs hover:bg-muted"
          onClick={() => setListDialogOpen(true)}
        >
          <ListIcon className="size-3.5" />
          <span className="max-w-[140px] truncate">
            {selectedList?.name ?? "Select List"}
          </span>
        </button>

        <ListSelectionDialog
          open={listDialogOpen}
          onOpenChange={setListDialogOpen}
          selectedId={effectiveListId}
          onSelect={(id) => onSettingsChange({ listId: id })}
        />

        <select
          className="h-7 rounded-sm border border-border bg-background px-2 text-xs"
          value={defaultsMerged.timeframe}
          onChange={(e) => onSettingsChange({ timeframe: e.target.value })}
        >
          {TIMEFRAME_OPTIONS.map((tf) => (
            <option key={tf} value={tf}>
              {tf}
            </option>
          ))}
        </select>

        <select
          className="h-7 rounded-sm border border-border bg-background px-2 text-xs"
          value={defaultsMerged.scaleMode}
          onChange={(e) =>
            onSettingsChange({
              scaleMode: e.target.value as MiniChartSettings["scaleMode"],
            })
          }
        >
          <option value="linear">Linear</option>
          <option value="log">Log</option>
        </select>

        <select
          className="h-7 rounded-sm border border-border bg-background px-2 text-xs"
          value={defaultsMerged.sortKey}
          onChange={(e) => onSettingsChange({ sortKey: e.target.value })}
        >
          {sortColumns.map((col) => (
            <option key={col.id} value={col.id}>
              Sort: {col.name}
            </option>
          ))}
        </select>

        <button
          className="h-7 rounded-sm border border-border px-2 text-xs hover:bg-muted"
          onClick={() =>
            onSettingsChange({
              sortDirection:
                defaultsMerged.sortDirection === "asc" ? "desc" : "asc",
            })
          }
        >
          {defaultsMerged.sortDirection === "asc" ? "Asc" : "Desc"}
        </button>

        <select
          className="h-7 rounded-sm border border-border bg-background px-2 text-xs"
          value={defaultsMerged.gridColumns}
          onChange={(e) =>
            onSettingsChange({ gridColumns: clampGridColumns(Number(e.target.value)) })
          }
        >
          {GRID_OPTIONS.map((cols) => (
            <option key={cols} value={cols}>
              {cols} cols
            </option>
          ))}
        </select>

        <div className="ml-auto" />

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button className="h-7 rounded-sm border border-border px-2 text-xs inline-flex items-center gap-1 hover:bg-muted">
              <SlidersHorizontal className="size-3.5" />
              Configure
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-72 p-3 space-y-3">
            <div>
              <p className="text-xs font-semibold">Header Values (max 4)</p>
              <div className="mt-2 grid grid-cols-1 gap-1">
                {screenerColumns.map((col) => {
                  const checked = defaultsMerged.headerColumnIds.includes(col.id);
                  return (
                    <label
                      key={col.id}
                      className="flex items-center gap-2 text-xs cursor-pointer"
                    >
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => handleHeaderToggle(col.id)}
                      />
                      <span className="truncate">{col.name}</span>
                    </label>
                  );
                })}
              </div>
            </div>

            <div>
              <p className="text-xs font-semibold">Moving Averages</p>
              <div className="mt-2 flex items-center gap-2">
                <button
                  className="h-6 rounded border border-border px-2 text-[11px] inline-flex items-center gap-1 hover:bg-muted"
                  onClick={() => addMA("ema")}
                >
                  <Plus className="size-3" />
                  EMA
                </button>
                <button
                  className="h-6 rounded border border-border px-2 text-[11px] inline-flex items-center gap-1 hover:bg-muted"
                  onClick={() => addMA("sma")}
                >
                  <Plus className="size-3" />
                  SMA
                </button>
              </div>
              <div className="mt-2 space-y-2">
                {defaultsMerged.maConfigs.map((ma) => (
                  <div key={ma.id} className="flex items-center gap-2 text-xs">
                    <input
                      type="checkbox"
                      checked={ma.enabled}
                      onChange={(e) => updateMA(ma.id, { enabled: e.target.checked })}
                    />
                    <span className="w-14">{ma.id}</span>
                    <select
                      value={ma.maType}
                      className="h-6 w-16 rounded border border-border bg-background px-1"
                      onChange={(e) =>
                        updateMAType(ma.id, e.target.value as MiniChartMAType)
                      }
                    >
                      <option value="ema">EMA</option>
                      <option value="sma">SMA</option>
                    </select>
                    <input
                      type="number"
                      min={2}
                      value={ma.length}
                      className="h-6 w-16 rounded border border-border bg-background px-1"
                      onChange={(e) => updateMA(ma.id, { length: Number(e.target.value) })}
                    />
                    <input
                      type="color"
                      value={ma.color}
                      className="h-6 w-8 rounded border border-border bg-background px-0"
                      onChange={(e) => updateMA(ma.id, { color: e.target.value })}
                    />
                    <button
                      className="h-6 w-6 rounded border border-border inline-flex items-center justify-center hover:bg-muted"
                      onClick={() => removeMA(ma.id)}
                      title="Remove MA"
                    >
                      <Trash2 className="size-3" />
                    </button>
                  </div>
                ))}
                {defaultsMerged.maConfigs.length === 0 && (
                  <p className="text-[11px] text-muted-foreground">No MA lines configured.</p>
                )}
              </div>
            </div>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      <div ref={scrollRef} className="flex-1 overflow-auto">
        {!sessionReady || !session ? (
          <div className="h-full flex items-center justify-center text-sm text-muted-foreground">
            Initializing chart session...
          </div>
        ) : !effectiveListId ? (
          <div className="h-full flex items-center justify-center text-sm text-muted-foreground">
            Select a list to start screening.
          </div>
        ) : isLoading ? (
          <div className="h-full flex items-center justify-center text-sm text-muted-foreground">
            Loading screener values...
          </div>
        ) : displayRows.length === 0 ? (
          <div className="h-full flex items-center justify-center text-sm text-muted-foreground">
            No symbols available.
          </div>
        ) : (
          <div
            className="relative"
            style={{
              height: `${rowVirtualizer.getTotalSize()}px`,
            }}
          >
            {rowVirtualizer.getVirtualItems().map((virtualRow) => {
              const start = virtualRow.index * defaultsMerged.gridColumns;
              const rowItems = displayRows.slice(
                start,
                start + defaultsMerged.gridColumns,
              );

              return (
                <div
                  key={virtualRow.key}
                  className="absolute left-0 right-0 px-2 py-1"
                  style={{
                    transform: `translateY(${virtualRow.start}px)`,
                    height: `${virtualRow.size}px`,
                  }}
                >
                  <div
                    className="grid gap-2 h-full"
                    style={{
                      gridTemplateColumns: `repeat(${defaultsMerged.gridColumns}, minmax(0, 1fr))`,
                    }}
                  >
                    {rowItems.map((row) => {
                      const symbolKey = row.ticker.toUpperCase();
                      const symbolAlerts = alertMap.get(symbolKey) ?? [];

                      return (
                        <MiniChartTile
                          key={row.ticker}
                          symbol={row.ticker}
                          name={row.name}
                          logo={row.logo}
                          headerValues={getHeaderValues(row)}
                          timeframe={defaultsMerged.timeframe}
                          scaleMode={defaultsMerged.scaleMode}
                          maConfigs={defaultsMerged.maConfigs}
                          session={session}
                          active
                          flagColor={getFlagColor(row.ticker)}
                          isSelected={activeSymbol === row.ticker.toUpperCase()}
                          isDark={isDark}
                          alerts={symbolAlerts}
                          onSelectSymbol={setChannelSymbol}
                          onToggleFlag={handleToggleFlag}
                          onSelectFlagColor={handleSelectFlagColor}
                          onCreateAlert={handleCreateAlert}
                          onModifyAlert={handleModifyAlert}
                          onDeleteAlert={handleDeleteAlert}
                        />
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
