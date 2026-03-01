import { useMemo, useRef, useEffect, useState } from "react";
import type { ScreenerFilterRow, ScreenerValues } from "@/types/ws";
import type { ColumnDef as ColumnDefModel } from "@/types/models";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ChevronUp, ChevronDown, Check, Plus } from "lucide-react";
import {
  ContextMenu,
  ContextMenuContent,
  ContextMenuItem,
  ContextMenuTrigger,
  ContextMenuSub,
  ContextMenuSubContent,
  ContextMenuSubTrigger,
} from "@/components/ui/context-menu";
import { useAuthStore } from "@/stores/auth-store";
import { toast } from "sonner";

type SortDirection = "asc" | "desc" | null;

interface SortConfig {
  key: string | null;
  direction: SortDirection;
}

interface ScreenerTableProps {
  tickers: ScreenerFilterRow[];
  values: ScreenerValues;
  columns: ColumnDefModel[];
  isLoading: boolean;
}

export function ScreenerTable({
  tickers,
  values,
  columns,
  isLoading,
}: ScreenerTableProps) {
  const [sortConfig, setSortConfig] = useState<SortConfig>({
    key: "ticker",
    direction: "asc",
  });

  const visibleColumns = useMemo(
    () => columns.filter((c) => c.visible !== false),
    [columns],
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
      } else if (key === "name") {
        valA = tickers[a].name ?? "";
        valB = tickers[b].name ?? "";
      } else {
        valA = values[key]?.[a];
        valB = values[key]?.[b];
      }

      if (valA === valB) return 0;
      if (valA == null) return 1;
      if (valB == null) return -1;

      const multiplier = direction === "asc" ? 1 : -1;

      // Handle strings vs other types
      if (typeof valA === "string" && typeof valB === "string") {
        return valA.localeCompare(valB) * multiplier;
      }

      return (valA < valB ? -1 : 1) * multiplier;
    });
  }, [tickers, values, sortConfig]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center space-y-3">
          <svg
            className="animate-spin h-8 w-8 text-primary mx-auto"
            viewBox="0 0 24 24"
          >
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
              fill="none"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"
            />
          </svg>
          <p className="text-sm text-muted-foreground">
            Loading screener data...
          </p>
        </div>
      </div>
    );
  }

  if (tickers.length === 0) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center space-y-2">
          <p className="text-sm text-muted-foreground">No symbols found</p>
          <p className="text-xs text-muted-foreground/60">
            The selected list may be empty
          </p>
        </div>
      </div>
    );
  }

  const renderSortIcon = (key: string) => {
    if (sortConfig.key !== key) return null;
    return sortConfig.direction === "asc" ? (
      <ChevronUp className="w-3 h-3 ml-1" />
    ) : (
      <ChevronDown className="w-3 h-3 ml-1" />
    );
  };

  return (
    <div className="h-full overflow-auto scrollbar-thin pb-10">
      <Table>
        <TableHeader className="sticky top-0 z-10 bg-card">
          <TableRow className="hover:bg-transparent border-b border-border">
            <TableHead
              onClick={() => handleSort("ticker")}
              className="w-32 text-xs font-bold h-8 sticky left-0 bg-card z-20 cursor-pointer hover:text-foreground transition-colors group"
            >
              <div className="flex items-center">
                Ticker
                {renderSortIcon("ticker")}
              </div>
            </TableHead>
            <TableHead
              onClick={() => handleSort("name")}
              className="w-48 text-xs font-bold h-8 cursor-pointer hover:text-foreground transition-colors group"
            >
              <div className="flex items-center">
                Name
                {renderSortIcon("name")}
              </div>
            </TableHead>
            {visibleColumns.map((col) => (
              <TableHead
                key={col.id}
                onClick={() => handleSort(col.id)}
                className="text-xs font-bold h-8 text-right min-w-[80px] cursor-pointer hover:text-foreground transition-colors group"
              >
                <div className="flex items-center justify-end">
                  {col.name}
                  {renderSortIcon(col.id)}
                </div>
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {sortedIndices.map((originalIndex) => {
            const ticker = tickers[originalIndex];
            return (
              <ScreenerRow
                key={ticker.ticker}
                ticker={ticker}
                rowIndex={originalIndex}
                columns={visibleColumns}
                values={values}
              />
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}

interface ScreenerRowProps {
  ticker: ScreenerFilterRow;
  rowIndex: number;
  columns: ColumnDefModel[];
  values: ScreenerValues;
}

function ScreenerRow({ ticker, rowIndex, columns, values }: ScreenerRowProps) {
  const allLists = useAuthStore((s) => s.lists);
  const lists = useMemo(
    () => allLists.filter((l) => l.type === "simple"),
    [allLists],
  );
  const addSymbolToList = useAuthStore((s) => s.addSymbolToList);
  const removeSymbolFromList = useAuthStore((s) => s.removeSymbolFromList);

  const handleToggle = async (
    listId: string,
    listName: string,
    inList: boolean,
  ) => {
    try {
      if (inList) {
        await removeSymbolFromList(listId, ticker.ticker);
        toast.success(`Removed ${ticker.ticker} from ${listName}`);
      } else {
        await addSymbolToList(listId, ticker.ticker);
        toast.success(`Added ${ticker.ticker} to ${listName}`);
      }
    } catch (err) {
      toast.error(`Failed to update list`);
    }
  };

  return (
    <ContextMenu>
      <ContextMenuTrigger asChild>
        <TableRow className="hover:bg-muted/30 border-b border-border/50 transition-colors cursor-context-menu">
          <TableCell className="font-mono text-xs font-medium py-1.5 sticky left-0 bg-background z-10">
            <span className="text-primary">{ticker.ticker}</span>
          </TableCell>
          <TableCell className="text-xs text-muted-foreground py-1.5 truncate max-w-[200px]">
            {ticker.name}
          </TableCell>
          {columns.map((col) => {
            const colValues = values[col.id];
            const value = colValues?.[rowIndex];
            return <ScreenerCell key={col.id} value={value} type={col.type} />;
          })}
        </TableRow>
      </ContextMenuTrigger>
      <ContextMenuContent className="w-56">
        <ContextMenuSub>
          <ContextMenuSubTrigger>
            <Plus className="mr-2 h-4 w-4" />
            Add to List
          </ContextMenuSubTrigger>
          <ContextMenuSubContent className="w-48">
            {lists.map((list) => {
              const inList = list.symbols.includes(ticker.ticker);
              return (
                <ContextMenuItem
                  key={list.id}
                  onClick={(e) => {
                    e.preventDefault(); // Keep menu open if desired, but default is to close
                    handleToggle(list.id, list.name, inList);
                  }}
                >
                  <div className="flex items-center justify-between w-full">
                    <span className="truncate">{list.name}</span>
                    {inList && <Check className="h-4 w-4 text-primary ml-2" />}
                  </div>
                </ContextMenuItem>
              );
            })}
            {lists.length === 0 && (
              <ContextMenuItem
                disabled
                className="text-xs text-muted-foreground"
              >
                No simple lists
              </ContextMenuItem>
            )}
          </ContextMenuSubContent>
        </ContextMenuSub>
      </ContextMenuContent>
    </ContextMenu>
  );
}

interface ScreenerCellProps {
  value: unknown;
  type: string;
}

function ScreenerCell({ value, type }: ScreenerCellProps) {
  const prevValueRef = useRef(value);
  const [flashClass, setFlashClass] = useState("");

  useEffect(() => {
    if (
      prevValueRef.current !== value &&
      typeof value === "number" &&
      typeof prevValueRef.current === "number"
    ) {
      const direction =
        value > prevValueRef.current ? "cell-flash-up" : "cell-flash-down";
      setFlashClass(direction);
      const timer = setTimeout(() => setFlashClass(""), 600);
      prevValueRef.current = value;
      return () => clearTimeout(timer);
    }
    prevValueRef.current = value;
  }, [value]);

  if (type === "condition") {
    return (
      <TableCell className={`text-right text-xs py-1.5 ${flashClass}`}>
        {value === true ? (
          <span className="text-success">✅</span>
        ) : value === false ? (
          <span className="text-destructive">❌</span>
        ) : (
          <span className="text-muted-foreground">—</span>
        )}
      </TableCell>
    );
  }

  // Numeric value
  const numValue = typeof value === "number" ? value : null;
  const formatted =
    numValue !== null
      ? numValue >= 1_000_000
        ? `${(numValue / 1_000_000).toFixed(1)}M`
        : numValue >= 1_000
          ? `${(numValue / 1_000).toFixed(1)}K`
          : numValue.toFixed(2)
      : value != null
        ? String(value)
        : "—";

  // Color for percentage-like columns
  const isPercentage = typeof value === "number" && Math.abs(value) < 100;
  const colorClass =
    isPercentage && numValue !== null
      ? numValue > 0
        ? "text-success"
        : numValue < 0
          ? "text-destructive"
          : ""
      : "";

  return (
    <TableCell
      className={`text-right font-mono text-xs py-1.5 tabular-nums ${colorClass} ${flashClass}`}
    >
      {formatted}
    </TableCell>
  );
}
