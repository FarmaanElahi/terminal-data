import { useMemo, useState, useCallback, useRef, useEffect } from "react";
import { useAuthStore } from "@/stores/auth-store";
import { useScreener } from "@/hooks/use-screener";
import { columnsApi } from "@/lib/api";
import type { WidgetProps } from "@/types/layout";
import type { ColumnDef, FilterState } from "@/types/models";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Filter, Settings, ChevronUp, ChevronDown } from "lucide-react";
import { ColumnEditor } from "./column-editor";
import { ScreenerStatus } from "@/components/screener/screener-status";

// ─── Value Formatter ─────────────────────────────────────────────────

function formatValue(val: unknown, col?: ColumnDef): React.ReactNode {
  if (val == null) return "—";
  if (typeof val === "boolean") return val ? "✓" : "✗";
  if (typeof val === "number") {
    if (!Number.isFinite(val)) return "—";

    let formatted = "";
    const absVal = Math.abs(val);

    const localeOptions: Intl.NumberFormatOptions = {
      maximumFractionDigits: 2,
      minimumFractionDigits: 2,
    };

    if (absVal >= 1_000_000) {
      localeOptions.minimumFractionDigits = 0;
    } else if (absVal < 1) {
      localeOptions.maximumFractionDigits = 4;
    }

    formatted = val.toLocaleString("en-US", localeOptions);

    // Apply show positive sign
    if (col?.display_numeric_show_positive_sign && val > 0) {
      formatted = "+" + formatted;
    }

    // Apply prefix/suffix
    const prefix = col?.display_numeric_prefix ?? "";
    const suffix = col?.display_numeric_suffix ?? "";

    return (
      <span
        style={{
          color:
            val > 0
              ? col?.display_numeric_positive_color || undefined
              : val < 0
                ? col?.display_numeric_negative_color || undefined
                : undefined,
        }}
      >
        {prefix}
        {formatted}
        {suffix}
      </span>
    );
  }
  return String(val);
}

const FILTER_CYCLE: Record<FilterState, FilterState> = {
  off: "active",
  active: "inactive",
  inactive: "off",
};

const FILTER_INDICATOR: Record<FilterState, string> = {
  off: "",
  active: "text-green-500",
  inactive: "text-red-500",
};

type SortDirection = "asc" | "desc" | null;

interface SortConfig {
  key: string | null;
  direction: SortDirection;
}

export function ScreenerWidget({
  instanceId,
  settings,
  onSettingsChange,
}: WidgetProps) {
  const s = (settings ?? {}) as Record<string, unknown>;
  const lists = useAuthStore((st) => st.lists);
  const columnSets = useAuthStore((st) => st.columnSets);
  const [editorOpen, setEditorOpen] = useState(false);
  const tableRef = useRef<HTMLTableElement>(null);
  const [sortConfig, setSortConfig] = useState<SortConfig>({
    key: "ticker",
    direction: "asc",
  });
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);
  const selectedRowRef = useRef<HTMLTableRowElement>(null);

  const listId = (s.listId as string) ?? lists?.[0]?.id ?? null;
  const columnSetId = (s.columnSetId as string) ?? columnSets?.[0]?.id ?? null;

  const selectedColumnSet = useMemo(
    () => columnSets?.find((cs) => cs.id === columnSetId) ?? null,
    [columnSets, columnSetId],
  );

  const columnMap = useMemo(() => {
    const map = new Map<string, ColumnDef>();
    if (selectedColumnSet?.columns) {
      for (const col of selectedColumnSet.columns) {
        map.set(col.id, col);
      }
    }
    return map;
  }, [selectedColumnSet]);

  const visibleColumns = useMemo(() => {
    if (!selectedColumnSet?.columns) return [];
    return selectedColumnSet.columns
      .filter((c) => c.visible !== false)
      .map((c) => c.id);
  }, [selectedColumnSet]);

  const { tickers, values, isLoading, lastUpdate, totalSymbols } = useScreener(
    instanceId,
    listId,
    selectedColumnSet?.columns || null,
  );

  const handleSort = (key: string) => {
    setSortConfig((prev) => {
      if (prev.key === key) {
        if (prev.direction === "asc") return { key, direction: "desc" };
        if (prev.direction === "desc") return { key: null, direction: null };
      }
      return { key, direction: "asc" };
    });
  };

  const sortedIndices = useMemo(() => {
    const indices = tickers.map((_, i) => i);
    const { key, direction } = sortConfig;
    if (!key || !direction) return indices;

    return [...indices].sort((a, b) => {
      let valA: any;
      let valB: any;

      if (key === "ticker") {
        valA = tickers[a].ticker;
        valB = tickers[b].ticker;
      } else {
        valA = values[key]?.[a];
        valB = values[key]?.[b];
      }

      if (valA === valB) return 0;
      if (valA == null) return 1;
      if (valB == null) return -1;

      const multiplier = direction === "asc" ? 1 : -1;
      if (typeof valA === "string" && typeof valB === "string") {
        return valA.localeCompare(valB) * multiplier;
      }
      return (valA < valB ? -1 : 1) * multiplier;
    });
  }, [tickers, values, sortConfig]);

  const handleFilterToggle = useCallback(
    async (colId: string) => {
      if (!selectedColumnSet) return;
      const col = columnMap.get(colId);
      if (!col || col.type !== "condition") return;

      const nextFilter = FILTER_CYCLE[col.filter ?? "off"];
      const updatedColumns = selectedColumnSet.columns.map((c) =>
        c.id === colId ? { ...c, filter: nextFilter } : c,
      );

      try {
        const { data } = await columnsApi.update(selectedColumnSet.id, {
          columns: updatedColumns,
        });
        useAuthStore.setState((state) => ({
          columnSets: state.columnSets.map((cs) =>
            cs.id === selectedColumnSet.id ? data : cs,
          ),
        }));
      } catch (err) {
        console.error("Failed to update filter:", err);
      }
    },
    [selectedColumnSet, columnMap],
  );

  const onResizeStart = useCallback(
    (e: React.MouseEvent, colId: string, currentWidth: number) => {
      e.preventDefault();
      e.stopPropagation();

      const startX = e.clientX;
      let finalWidth = currentWidth;

      const onMouseMove = (moveEvent: MouseEvent) => {
        const delta = moveEvent.clientX - startX;
        finalWidth = Math.max(10, currentWidth + delta);

        if (tableRef.current) {
          // Find the specific column in the table (including ticker)
          const ths = tableRef.current.querySelectorAll("th");
          const idx =
            colId === "ticker"
              ? 0
              : visibleColumns.indexOf(colId) + (colId === "ticker" ? 0 : 1);

          if (ths[idx]) {
            ths[idx].style.width = `${finalWidth}px`;
          }
        }
      };

      const onMouseUp = () => {
        window.removeEventListener("mousemove", onMouseMove);
        window.removeEventListener("mouseup", onMouseUp);

        if (colId === "ticker") {
          onSettingsChange({ ticker_width: finalWidth });
        } else if (selectedColumnSet) {
          useAuthStore.setState((state) => ({
            columnSets: state.columnSets.map((cs) => {
              if (cs.id !== selectedColumnSet.id) return cs;
              return {
                ...cs,
                columns: cs.columns.map((c) =>
                  c.id === colId
                    ? { ...c, display_column_width: finalWidth }
                    : c,
                ),
              };
            }),
          }));
        }
      };

      window.addEventListener("mousemove", onMouseMove);
      window.addEventListener("mouseup", onMouseUp);
    },
    [onSettingsChange, selectedColumnSet, visibleColumns],
  );

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (sortedIndices.length === 0) return;

    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelectedIndex((prev) => {
        if (prev === null) return 0;
        return Math.min(prev + 1, sortedIndices.length - 1);
      });
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedIndex((prev) => {
        if (prev === null) return 0;
        return Math.max(prev - 1, 0);
      });
    }
  };

  useEffect(() => {
    if (selectedIndex !== null && selectedRowRef.current) {
      selectedRowRef.current.scrollIntoView({
        block: "nearest",
        behavior: "smooth",
      });
    }
  }, [selectedIndex]);

  const renderSortIcon = (key: string) => {
    if (sortConfig.key !== key) return null;
    return sortConfig.direction === "asc" ? (
      <ChevronUp className="w-2.5 h-2.5 ml-1" />
    ) : (
      <ChevronDown className="w-2.5 h-2.5 ml-1" />
    );
  };

  return (
    <div className="flex flex-col h-full relative">
      <div className="flex items-center gap-2 p-2 border-b border-border shrink-0">
        <Select
          value={listId ?? ""}
          onValueChange={(v) => onSettingsChange({ listId: v })}
        >
          <SelectTrigger className="h-7 w-40 text-xs">
            <SelectValue placeholder="Select list" />
          </SelectTrigger>
          <SelectContent>
            {lists?.map((l) => (
              <SelectItem key={l.id} value={l.id}>
                {l.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select
          value={columnSetId ?? ""}
          onValueChange={(v) => onSettingsChange({ columnSetId: v })}
        >
          <SelectTrigger className="h-7 w-40 text-xs">
            <SelectValue placeholder="Select columns" />
          </SelectTrigger>
          <SelectContent>
            {columnSets?.map((cs) => (
              <SelectItem key={cs.id} value={cs.id}>
                {cs.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <div className="flex-1" />

        <button
          onClick={() => setEditorOpen(true)}
          className="p-1 rounded-sm text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
          title="Edit columns"
        >
          <Settings className="w-3.5 h-3.5" />
        </button>
      </div>

      <div
        className="flex-1 overflow-auto pb-10 outline-none focus-within:ring-1 focus-within:ring-primary/20"
        tabIndex={0}
        onKeyDown={handleKeyDown}
      >
        {tickers.length === 0 && !isLoading ? (
          <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
            No data
          </div>
        ) : (
          <table ref={tableRef} className="w-max text-xs table-fixed">
            <thead>
              <tr className="border-b border-border sticky top-0 bg-card z-10">
                <th
                  style={{
                    width: (s.ticker_width as number) ?? 100,
                  }}
                  className="text-left p-1.5 font-medium text-muted-foreground transition-colors group relative overflow-hidden whitespace-nowrap"
                >
                  <div
                    className="flex items-center h-full cursor-pointer hover:text-foreground truncate"
                    onClick={() => handleSort("ticker")}
                  >
                    Ticker
                    {renderSortIcon("ticker")}
                  </div>
                  <div
                    onMouseDown={(e) =>
                      onResizeStart(
                        e,
                        "ticker",
                        (s.ticker_width as number) ?? 100,
                      )
                    }
                    className="absolute right-0 top-0 bottom-0 w-2 cursor-col-resize hover:bg-primary/30 active:bg-primary/50 transition-colors z-20"
                  />
                  <div className="absolute right-0 top-1 bottom-1 w-px bg-border group-hover:bg-primary/50 transition-colors pointer-events-none" />
                </th>
                {visibleColumns.map((colId) => {
                  const col = columnMap.get(colId);
                  const hasFilter = col?.type === "condition";
                  const filterState = col?.filter ?? "off";

                  return (
                    <th
                      key={colId}
                      style={{
                        width: col?.display_column_width ?? 100,
                      }}
                      className="text-right p-1.5 font-medium text-muted-foreground group/col relative overflow-hidden whitespace-nowrap"
                    >
                      <div className="flex items-center justify-end gap-1">
                        {hasFilter && (
                          <button
                            onClick={() => handleFilterToggle(colId)}
                            className={`p-0.5 rounded-sm hover:bg-muted transition-all ${
                              filterState === "off"
                                ? "opacity-0 group-hover/col:opacity-50"
                                : FILTER_INDICATOR[filterState]
                            }`}
                            title={`Filter: ${filterState}`}
                          >
                            <Filter className="w-2.5 h-2.5" />
                          </button>
                        )}
                        <span
                          onClick={() => handleSort(colId)}
                          className="cursor-pointer hover:text-foreground transition-colors inline-flex items-center truncate"
                        >
                          {col?.name ?? colId}
                          {renderSortIcon(colId)}
                        </span>
                      </div>
                      <div
                        onMouseDown={(e) =>
                          onResizeStart(
                            e,
                            colId,
                            col?.display_column_width ?? 100,
                          )
                        }
                        className="absolute right-0 top-0 bottom-0 w-2 cursor-col-resize hover:bg-primary/30 active:bg-primary/50 transition-colors z-20"
                      />
                      <div className="absolute right-0 top-1 bottom-1 w-px bg-border group-hover/col:bg-primary/50 transition-colors pointer-events-none" />
                    </th>
                  );
                })}
              </tr>
            </thead>
            <tbody>
              {sortedIndices.map((originalIndex, i) => {
                const row = tickers[originalIndex];
                const isSelected = i === selectedIndex;
                return (
                  <tr
                    key={row.ticker}
                    ref={isSelected ? selectedRowRef : null}
                    className={`border-b border-border/50 transition-colors ${
                      isSelected ? "bg-primary/10" : "hover:bg-muted/30"
                    }`}
                  >
                    <td
                      style={{
                        width: (s.ticker_width as number) ?? 100,
                      }}
                      className="p-1.5 font-medium text-foreground truncate"
                    >
                      <div className="flex items-center gap-2">
                        {row.logo ? (
                          <img
                            src={`https://s3-symbol-logo.tradingview.com/${row.logo}.svg`}
                            alt=""
                            className="w-4 h-4 rounded-full bg-muted shrink-0"
                            onError={(e) => {
                              (e.target as HTMLImageElement).style.display =
                                "none";
                            }}
                          />
                        ) : (
                          <div className="w-4 h-4 rounded-full bg-primary/20 flex items-center justify-center text-[8px] text-primary shrink-0">
                            {row.ticker.substring(0, 1)}
                          </div>
                        )}
                        <div className="flex items-center min-w-0">
                          <span className="truncate">
                            {row.ticker.includes(":")
                              ? row.ticker.split(":")[1]
                              : row.ticker}
                          </span>
                        </div>
                      </div>
                    </td>
                    {visibleColumns.map((colId) => {
                      const col = columnMap.get(colId);
                      return (
                        <td
                          key={colId}
                          style={{
                            width: col?.display_column_width ?? 100,
                          }}
                          className="p-1.5 text-right tabular-nums text-muted-foreground truncate"
                        >
                          {formatValue(values[colId]?.[originalIndex], col)}
                        </td>
                      );
                    })}
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      <ScreenerStatus
        filteredSymbols={tickers.length}
        totalSymbols={totalSymbols}
        lastUpdate={lastUpdate}
        isLoading={isLoading}
      />

      {selectedColumnSet && (
        <ColumnEditor
          open={editorOpen}
          onClose={() => setEditorOpen(false)}
          columnSet={selectedColumnSet}
        />
      )}
    </div>
  );
}
