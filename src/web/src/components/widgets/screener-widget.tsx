import { useMemo, useState, useCallback } from "react";
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

function formatValue(val: unknown): string {
  if (val == null) return "—";
  if (typeof val === "boolean") return val ? "✓" : "✗";
  if (typeof val === "number") {
    if (!Number.isFinite(val)) return "—";
    if (Math.abs(val) >= 1_000_000) {
      return val.toLocaleString("en-US", {
        maximumFractionDigits: 2,
        minimumFractionDigits: 0,
      });
    }
    if (Math.abs(val) >= 100) {
      return val.toLocaleString("en-US", {
        maximumFractionDigits: 2,
        minimumFractionDigits: 2,
      });
    }
    if (Math.abs(val) >= 1) {
      return val.toLocaleString("en-US", {
        maximumFractionDigits: 2,
        minimumFractionDigits: 2,
      });
    }
    return val.toLocaleString("en-US", {
      maximumFractionDigits: 4,
      minimumFractionDigits: 2,
    });
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
  const [sortConfig, setSortConfig] = useState<SortConfig>({
    key: "ticker",
    direction: "asc",
  });

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

      <div className="flex-1 overflow-auto pb-10">
        {tickers.length === 0 && !isLoading ? (
          <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
            No data
          </div>
        ) : (
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-border sticky top-0 bg-card z-10">
                <th
                  onClick={() => handleSort("ticker")}
                  className="text-left p-1.5 font-medium text-muted-foreground cursor-pointer hover:text-foreground transition-colors group"
                >
                  <div className="flex items-center">
                    Ticker
                    {renderSortIcon("ticker")}
                  </div>
                </th>
                {visibleColumns.map((colId) => {
                  const col = columnMap.get(colId);
                  const hasFilter = col?.type === "condition";
                  const filterState = col?.filter ?? "off";

                  return (
                    <th
                      key={colId}
                      className="text-right p-1.5 font-medium text-muted-foreground group/col"
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
                          className="cursor-pointer hover:text-foreground transition-colors inline-flex items-center"
                        >
                          {col?.name ?? colId}
                          {renderSortIcon(colId)}
                        </span>
                      </div>
                    </th>
                  );
                })}
              </tr>
            </thead>
            <tbody>
              {sortedIndices.map((originalIndex) => {
                const row = tickers[originalIndex];
                return (
                  <tr
                    key={row.ticker}
                    className="border-b border-border/50 hover:bg-muted/30 transition-colors"
                  >
                    <td className="p-1.5 font-medium text-foreground">
                      {row.ticker}
                    </td>
                    {visibleColumns.map((colId) => (
                      <td
                        key={colId}
                        className="p-1.5 text-right tabular-nums text-muted-foreground"
                      >
                        {formatValue(values[colId]?.[originalIndex])}
                      </td>
                    ))}
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
