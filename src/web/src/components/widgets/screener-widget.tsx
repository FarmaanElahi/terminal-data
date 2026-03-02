import React, {
  useMemo,
  useState,
  useCallback,
  useRef,
  useEffect,
  useDeferredValue,
  memo,
} from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { cn } from "@/lib/utils";
import {
  useListsQuery,
  useAddSymbolMutation,
  useRemoveSymbolMutation,
  useSetFlagMutation,
  useSetSymbolsMutation,
  useCreateListMutation,
  useUpdateListMutation,
} from "@/queries/use-lists";
import { DEFAULT_SCREENER_COLUMNS } from "@/lib/register-widgets";
import { useScreener } from "@/hooks/use-screener";
import { useWidget } from "@/hooks/use-widget";
import type { WidgetProps } from "@/types/layout";
import type { ColumnDef, FilterState } from "@/types/models";
import type { ScreenerFilterRow, ScreenerValues } from "@/types/ws";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ListSelectionDialog } from "./list-selection-dialog";
import { Button } from "@/components/ui/button";
import {
  Filter,
  FilterX,
  Settings,
  ChevronUp,
  ChevronDown,
  Plus,
  Check,
  List as ListIcon,
  RefreshCw,
  MoreVertical,
  Download,
  Upload,
  Copy,
  Trash2,
  Pencil,
} from "lucide-react";
import {
  ContextMenu,
  ContextMenuContent,
  ContextMenuItem,
  ContextMenuTrigger,
  ContextMenuSub,
  ContextMenuSubContent,
  ContextMenuSubTrigger,
} from "@/components/ui/context-menu";
import {
  DropdownMenuItem,
  DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu";
import { toast } from "sonner";
import { ColumnEditor } from "./column-editor";
import { CreateListDialog } from "./create-list-dialog";
import { ScreenerStatus } from "@/components/screener/screener-status";

// ─── Value Formatter ─────────────────────────────────────────────────

function isWhite(color: string): boolean {
  const c = color.toLowerCase();
  return (
    c === "white" ||
    c === "#fff" ||
    c === "#ffffff" ||
    c === "rgb(255,255,255)" ||
    c === "rgba(255,255,255,1)"
  );
}

function isBlack(color: string): boolean {
  const c = color.toLowerCase();
  return (
    c === "black" ||
    c === "#000" ||
    c === "#000000" ||
    c === "rgb(0,0,0)" ||
    c === "rgba(0,0,0,1)"
  );
}

function formatValue(
  val: unknown,
  col?: ColumnDef,
  isDark = true,
): React.ReactNode {
  if (val == null) return "—";

  const adjustColor = (color: string | null | undefined) => {
    if (!color) return undefined;
    if (isDark && isBlack(color)) return "var(--foreground)";
    if (!isDark && isWhite(color)) return "var(--foreground)";
    return color;
  };

  const posColor = adjustColor(
    col?.display_numeric_positive_color ?? "#10b981",
  );
  const negColor = adjustColor(
    col?.display_numeric_negative_color ?? "#ef4444",
  );
  let finalColor = adjustColor(col?.display_color ?? "#ffffff");

  // Boolean handling
  if (typeof val === "boolean") {
    const boolColor = val ? posColor : negColor;
    return (
      <span style={{ color: boolColor }} className="font-bold">
        {val ? "✓" : "✗"}
      </span>
    );
  }

  // Numeric handling
  if (typeof val === "number") {
    if (!Number.isFinite(val)) return "—";

    let formatted = "";
    const absVal = Math.abs(val);

    const localeOptions: Intl.NumberFormatOptions = {
      maximumFractionDigits: col?.display_numeric_max_decimal ?? 2,
      minimumFractionDigits: col?.display_numeric_max_decimal ?? 2,
    };

    if (col?.display_numeric_max_decimal == null) {
      if (absVal >= 1_000_000) {
        localeOptions.minimumFractionDigits = 0;
      } else if (absVal < 1) {
        localeOptions.maximumFractionDigits = 4;
      }
    }

    formatted = val.toLocaleString("en-US", localeOptions);

    // Apply show positive sign
    if (col?.display_numeric_show_positive_sign && val > 0) {
      formatted = "+" + formatted;
    }

    // Apply specific numeric colors if defined
    if (val > 0) {
      finalColor = posColor;
    } else if (val < 0) {
      finalColor = negColor;
    }

    // Apply prefix/suffix
    const prefix = col?.display_numeric_prefix ?? "";
    const suffix = col?.display_numeric_suffix ?? "";

    return (
      <span style={{ color: finalColor }}>
        {prefix}
        {formatted}
        {suffix}
      </span>
    );
  }

  return <span style={{ color: finalColor }}>{String(val)}</span>;
}

function AnimatedValue({
  value,
  col,
  isDark,
}: {
  value: unknown;
  col?: ColumnDef;
  isDark: boolean;
}) {
  const [isFlashing, setIsFlashing] = useState(false);
  const prevValue = useRef(value);
  const resetTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    // Only flash if the functional value actually changed
    if (value !== prevValue.current) {
      prevValue.current = value;

      // Clear any pending reset timer
      if (resetTimerRef.current) {
        clearTimeout(resetTimerRef.current);
      }

      // Force reset if already flashing to restart the animation cleanly
      setIsFlashing(false);

      const timer = setTimeout(() => {
        setIsFlashing(true);
        resetTimerRef.current = setTimeout(() => {
          setIsFlashing(false);
          resetTimerRef.current = null;
        }, 800);
      }, 10); // Small delay to allow CSS reset

      return () => {
        clearTimeout(timer);
        if (resetTimerRef.current) clearTimeout(resetTimerRef.current);
      };
    }
  }, [value]);

  const formatted = useMemo(
    () => formatValue(value, col, isDark),
    [value, col, isDark],
  );

  return (
    <div
      className={cn(
        "transition-all duration-300 will-change-[transform,filter]",
        isFlashing && "font-bold scale-110 brightness-125",
      )}
    >
      {formatted}
    </div>
  );
}

// ─── Color Mapping ──────────────────────────────────────────────────

const FLAG_COLORS: Record<string, string> = {
  red: "text-red-500 fill-red-500",
  green: "text-green-500 fill-green-500",
  yellow: "text-yellow-500 fill-yellow-500",
  blue: "text-blue-500 fill-blue-500",
  purple: "text-purple-500 fill-purple-500",
};

// Custom Flag Icon matching user image (horizontal ribbon)
function FlagIcon({
  className,
  onClick,
}: {
  className?: string;
  onClick?: (e: React.MouseEvent) => void;
}) {
  return (
    <svg
      viewBox="0 0 24 24"
      preserveAspectRatio="none"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      onClick={onClick}
    >
      <path d="M0 0h24l-8 12 8 12H0V0z" fill="currentColor" />
    </svg>
  );
}

const COLOR_OPTIONS = [
  { label: "Red", value: "red", className: "bg-red-500" },
  { label: "Green", value: "green", className: "bg-green-500" },
  { label: "Yellow", value: "yellow", className: "bg-yellow-500" },
  { label: "Blue", value: "blue", className: "bg-blue-500" },
  { label: "Purple", value: "purple", className: "bg-purple-500" },
];

// ─── FlagCell Component ─────────────────────────────────────────────

interface FlagCellProps {
  ticker: string;
}

function FlagCell({ ticker }: FlagCellProps) {
  const { data: lists = [] } = useListsQuery();
  const removeSymbol = useRemoveSymbolMutation();
  const setFlag = useSetFlagMutation();
  const [popoverOpen, setPopoverOpen] = useState(false);

  // Find if this symbol is in any color list
  const colorList = useMemo(() => {
    return lists.find((l) => l.type === "color" && l.symbols.includes(ticker));
  }, [lists, ticker]);

  const currentColor = colorList?.color ?? null;

  const handleFlagClick = (e: React.MouseEvent) => {
    e.stopPropagation();

    if (currentColor && colorList) {
      removeSymbol.mutate({ listId: colorList.id, ticker });
      return;
    }

    const lastUsedColor = localStorage.getItem("last_flag_color") || "red";
    const targetList = lists.find(
      (l) => l.type === "color" && l.color === lastUsedColor,
    );
    if (targetList) {
      setFlag.mutate({ targetListId: targetList.id, ticker });
    }
  };

  const handleColorSelect = (color: string) => {
    setPopoverOpen(false);

    if (currentColor === color && colorList) {
      removeSymbol.mutate({ listId: colorList.id, ticker });
      return;
    }

    localStorage.setItem("last_flag_color", color);
    const targetList = lists.find(
      (l) => l.type === "color" && l.color === color,
    );
    if (targetList) {
      setFlag.mutate({ targetListId: targetList.id, ticker });
    }
  };

  return (
    <DropdownMenu open={popoverOpen} onOpenChange={setPopoverOpen}>
      <DropdownMenuTrigger asChild>
        <button
          onContextMenu={(e) => {
            e.preventDefault();
            setPopoverOpen(true);
          }}
          className={`group/flag relative h-full w-3 outline-none transition-opacity ${
            currentColor ? "opacity-100" : "opacity-0 group-hover:opacity-100"
          }`}
        >
          <FlagIcon
            onClick={handleFlagClick}
            className={`w-full h-full transition-all ${
              currentColor
                ? FLAG_COLORS[currentColor] || "text-primary/80"
                : "text-muted-foreground/10 hover:text-muted-foreground/20"
            }`}
          />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent
        className="w-auto p-2 flex gap-2 bg-card border-border"
        align="start"
      >
        {COLOR_OPTIONS.map((opt) => (
          <button
            key={opt.value}
            onClick={() => handleColorSelect(opt.value)}
            className={`w-5 h-5 rounded-full ${opt.className} hover:scale-110 transition-transform ${
              currentColor === opt.value
                ? "ring-2 ring-white ring-offset-1 ring-offset-background"
                : ""
            }`}
            title={opt.label}
          />
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

// ─── ScreenerRow Component ──────────────────────────────────────────
const ScreenerRow = memo(
  ({
    row,
    originalIndex,
    visualIndex,
    isSelected,
    onSelect,
    visibleColumns,
    columnMap,
    values,
    isDark,
    getColWidth,
    screenerListId,
    onListModified,
  }: {
    row: ScreenerFilterRow;
    originalIndex: number;
    visualIndex: number;
    isSelected: boolean;
    onSelect: (index: number, focus?: boolean) => void;
    visibleColumns: string[];
    columnMap: Map<string, ColumnDef>;
    values: ScreenerValues;
    isDark: boolean;
    getColWidth: (colId: string, fallback: number) => number;
    screenerListId: string | null;
    onListModified: () => void;
  }) => {
    const { data: allLists = [] } = useListsQuery();
    const lists = useMemo(
      () => allLists.filter((l) => l.type === "simple"),
      [allLists],
    );
    const addSymbol = useAddSymbolMutation();
    const removeSymbol = useRemoveSymbolMutation();

    const handleToggle = async (
      listId: string,
      listName: string,
      inList: boolean,
    ) => {
      try {
        if (inList) {
          await removeSymbol.mutateAsync({ listId, ticker: row.ticker });
          toast.success(`Removed ${row.ticker} from ${listName}`);
        } else {
          await addSymbol.mutateAsync({ listId, ticker: row.ticker });
          toast.success(`Added ${row.ticker} to ${listName}`);
          if (screenerListId) {
            onListModified();
          }
        }
      } catch {
        toast.error(`Failed to update list`);
      }
    };

    return (
      <ContextMenu>
        <ContextMenuTrigger asChild>
          <tr
            onClick={() => onSelect(visualIndex, true)}
            data-selected={isSelected}
            className="group border-b border-border/50 transition-colors hover:bg-muted/30 cursor-pointer data-[selected=true]:bg-primary/5 data-[selected=true]:ring-1 data-[selected=true]:ring-inset data-[selected=true]:ring-primary data-[selected=true]:relative data-[selected=true]:z-10 outline-none"
          >
            <td
              style={{
                width: getColWidth("ticker", 100),
                minWidth: getColWidth("ticker", 100),
                maxWidth: getColWidth("ticker", 100),
              }}
              className="p-1.5 font-medium text-foreground truncate"
            >
              <div className="flex items-center h-full gap-1">
                <FlagCell ticker={row.ticker} />
                <div className="flex items-center gap-2 flex-1 min-w-0 pr-1.5">
                  {row.logo ? (
                    <img
                      src={`https://s3-symbol-logo.tradingview.com/${row.logo}.svg`}
                      alt=""
                      className="w-4 h-4 rounded-full bg-muted shrink-0"
                      onError={(e) => {
                        (e.target as HTMLImageElement).style.display = "none";
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
              </div>
            </td>
            {visibleColumns.map((colId) => {
              const col = columnMap.get(colId);
              return (
                <td
                  key={colId}
                  style={{
                    width: getColWidth(colId, 100),
                    minWidth: getColWidth(colId, 100),
                    maxWidth: getColWidth(colId, 100),
                  }}
                  className="p-1.5 text-right tabular-nums text-muted-foreground truncate"
                >
                  <AnimatedValue
                    value={values[colId]?.[originalIndex]}
                    col={col}
                    isDark={isDark}
                  />
                </td>
              );
            })}
          </tr>
        </ContextMenuTrigger>
        <ContextMenuContent className="w-56">
          <ContextMenuSub>
            <ContextMenuSubTrigger>
              <Plus className="mr-2 h-4 w-4" />
              Add to List
            </ContextMenuSubTrigger>
            <ContextMenuSubContent className="w-48">
              {lists.map((list) => {
                const inList = list.symbols.includes(row.ticker);
                return (
                  <ContextMenuItem
                    key={list.id}
                    onClick={(e) => {
                      e.preventDefault();
                      handleToggle(list.id, list.name, inList);
                    }}
                  >
                    <div className="flex items-center justify-between w-full">
                      <span className="truncate">{list.name}</span>
                      {inList && (
                        <Check className="h-4 w-4 text-primary ml-2" />
                      )}
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
  },
);

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
  const { setChannelSymbol, channelContext } = useWidget(instanceId);
  const { data: lists = [] } = useListsQuery();
  const [editorOpen, setEditorOpen] = useState(false);
  const [createListOpen, setCreateListOpen] = useState(false);
  const [listDialogOpen, setListDialogOpen] = useState(false);
  const [filtersBypassed, setFiltersBypassed] = useState(
    () => (s.filtersBypassed as boolean) ?? false,
  );
  const tableRef = useRef<HTMLTableElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const [sortConfig, setSortConfig] = useState<SortConfig>({
    key: "ticker",
    direction: "asc",
  });
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);
  const setSymbolsMutation = useSetSymbolsMutation();
  const createListMutation = useCreateListMutation();
  const updateListMutation = useUpdateListMutation();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isRenaming, setIsRenaming] = useState(false);
  const [renameValue, setRenameValue] = useState("");

  const [isDark, setIsDark] = useState(true);

  // Live column widths during resize — overrides stored widths while dragging
  const [liveWidths, setLiveWidths] = useState<Record<string, number>>({});

  useEffect(() => {
    // Basic theme detection
    const theme =
      document.documentElement.classList.contains("dark") ||
      !document.documentElement.classList.contains("light");
    setIsDark(theme);
  }, []);

  const listId = (s.listId as string) ?? lists?.[0]?.id ?? null;
  const selectedList = useMemo(
    () => lists.find((l) => l.id === listId) ?? null,
    [lists, listId],
  );

  const isEditable =
    selectedList?.type === "simple" || selectedList?.type === "color";

  const columns =
    (s.columns as ColumnDef[] | undefined) ?? DEFAULT_SCREENER_COLUMNS;

  const columnMap = useMemo(() => {
    const map = new Map<string, ColumnDef>();
    for (const col of columns) {
      map.set(col.id, col);
    }
    return map;
  }, [columns]);

  const visibleColumns = useMemo(() => {
    return columns.filter((c) => c.visible !== false).map((c) => c.id);
  }, [columns]);

  const hasActiveFilters = useMemo(() => {
    return columns.some((c) => c.filter !== "off");
  }, [columns]);

  const effectiveColumns = useMemo(() => {
    if (!filtersBypassed) return columns;
    return columns.map((c) => ({ ...c, filter: "off" as FilterState }));
  }, [columns, filtersBypassed]);

  const filterActive = !filtersBypassed;

  const { tickers, values, isLoading, lastUpdate, totalSymbols, refresh } =
    useScreener(instanceId, listId, effectiveColumns, filterActive);

  // Defer high-frequency updates to keep the UI responsive during massive re-renders
  const deferredTickers = useDeferredValue(tickers);
  const deferredValues = useDeferredValue(values);

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
    if (deferredTickers.length === 0) return [];
    // Filter out ### section markers — sections are rendered by displayItems from sectionMap
    const indices = Array.from(
      { length: deferredTickers.length },
      (_, i) => i,
    ).filter((i) => !deferredTickers[i].ticker.startsWith("###"));
    const { key, direction } = sortConfig;

    const sortFn = (a: number, b: number): number => {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      let valA: any;
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      let valB: any;
      if (key === "ticker") {
        valA = deferredTickers[a].ticker;
        valB = deferredTickers[b].ticker;
      } else {
        valA = deferredValues[key ?? ""]?.[a];
        valB = deferredValues[key ?? ""]?.[b];
      }
      const multiplier = direction === "asc" ? 1 : -1;
      if (valA === valB) return (a - b) * multiplier;
      if (valA == null) return 1;
      if (valB == null) return -1;
      if (typeof valA === "string" && typeof valB === "string") {
        return valA.localeCompare(valB) * multiplier;
      }
      return (valA < valB ? -1 : 1) * multiplier;
    };

    if (!key || !direction) return indices;
    return indices.sort(sortFn);
  }, [deferredTickers, deferredValues, sortConfig]);

  // Committed display order — only updated on Resort click or when ticker count changes
  const [committedIndices, setCommittedIndices] = useState<number[]>([]);
  const sortedIndicesRef = useRef<number[]>(sortedIndices);
  sortedIndicesRef.current = sortedIndices;

  const prevTickerCountRef = useRef(0);
  useEffect(() => {
    const count = deferredTickers.length;
    if (count !== prevTickerCountRef.current) {
      prevTickerCountRef.current = count;
      setCommittedIndices([...sortedIndicesRef.current]);
    }
  }, [deferredTickers.length]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleResort = useCallback(() => {
    setCommittedIndices([...sortedIndicesRef.current]);
    if (scrollContainerRef.current) scrollContainerRef.current.scrollTop = 0;
  }, []);

  type DisplayItem = { type: "symbol"; tickerIndex: number };

  const displayItems = useMemo<DisplayItem[]>(() => {
    return committedIndices.map((idx) => ({
      type: "symbol" as const,
      tickerIndex: idx,
    }));
  }, [committedIndices]);

  // Select a row and update the linked channel symbol
  const handleSelect = useCallback(
    (displayIndex: number, focus = false) => {
      const item = displayItems[displayIndex];
      if (!item) return;
      setSelectedIndex(displayIndex);
      const ticker = deferredTickers[item.tickerIndex]?.ticker;
      if (ticker) {
        setChannelSymbol(ticker);
      }
      if (focus && scrollContainerRef.current) {
        scrollContainerRef.current.focus();
      }
    },
    [setChannelSymbol, deferredTickers, displayItems],
  );

  // Sync selected row when channel symbol changes from another widget
  const channelSymbol = channelContext?.symbol;
  useEffect(() => {
    if (!channelSymbol || displayItems.length === 0) return;
    const idx = displayItems.findIndex(
      (item) =>
        item.type === "symbol" &&
        deferredTickers[item.tickerIndex]?.ticker === channelSymbol,
    );
    if (idx !== -1 && idx !== selectedIndex) {
      setSelectedIndex(idx);
    }
    // Only react to channelSymbol changes, not internal selection changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [channelSymbol, displayItems, deferredTickers]);

  const handleFilterToggle = useCallback(
    (colId: string) => {
      const col = columnMap.get(colId);
      if (!col || col.type !== "condition") return;

      const nextFilter = FILTER_CYCLE[col.filter ?? "off"];
      const updatedColumns = columns.map((c) =>
        c.id === colId ? { ...c, filter: nextFilter } : c,
      );

      onSettingsChange({ columns: updatedColumns });
    },
    [columns, columnMap, onSettingsChange],
  );

  const onResizeStart = useCallback(
    (e: React.MouseEvent, colId: string, currentWidth: number) => {
      e.preventDefault();
      e.stopPropagation();

      const startX = e.clientX;

      const onMouseMove = (moveEvent: MouseEvent) => {
        const delta = moveEvent.clientX - startX;
        const newWidth = Math.max(40, currentWidth + delta);
        setLiveWidths((prev) => ({ ...prev, [colId]: newWidth }));
      };

      const onMouseUp = () => {
        window.removeEventListener("mousemove", onMouseMove);
        window.removeEventListener("mouseup", onMouseUp);

        // Read the final width from liveWidths
        setLiveWidths((prev) => {
          const finalWidth = prev[colId] ?? currentWidth;

          if (colId === "ticker") {
            onSettingsChange({ ticker_width: finalWidth });
          } else {
            const updatedColumns = columns.map((c) =>
              c.id === colId ? { ...c, display_column_width: finalWidth } : c,
            );
            onSettingsChange({ columns: updatedColumns });
          }

          // Clear the live width for this column
          const { [colId]: _, ...rest } = prev;
          return rest;
        });
      };

      window.addEventListener("mousemove", onMouseMove);
      window.addEventListener("mouseup", onMouseUp);
    },
    [onSettingsChange, columns],
  );

  // Helper to get effective column width (live during drag, stored otherwise)
  const getColWidth = useCallback(
    (colId: string, fallback: number) => {
      if (colId in liveWidths) return liveWidths[colId];
      if (colId === "ticker") return (s.ticker_width as number) ?? fallback;
      return columnMap.get(colId)?.display_column_width ?? fallback;
    },
    [liveWidths, s.ticker_width, columnMap],
  );

  const ROW_HEIGHT = 28; // px — matches p-1.5 + text-xs

  const rowVirtualizer = useVirtualizer({
    count: displayItems.length,
    getScrollElement: () => scrollContainerRef.current,
    estimateSize: () => ROW_HEIGHT,
    overscan: 15,
  });

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (displayItems.length === 0) return;

    const findNextSymbol = (start: number, dir: 1 | -1): number => {
      let i = start;
      while (i >= 0 && i < displayItems.length) {
        if (displayItems[i].type === "symbol") return i;
        i += dir;
      }
      return -1;
    };

    if (e.key === "ArrowDown" || e.key === " ") {
      e.preventDefault();
      const start = selectedIndex === null ? 0 : selectedIndex + 1;
      const next = findNextSymbol(start, 1);
      if (next !== -1) handleSelect(next);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      const start =
        selectedIndex === null ? displayItems.length - 1 : selectedIndex - 1;
      const next = findNextSymbol(start, -1);
      if (next !== -1) handleSelect(next);
    }
  };

  // Keep selected row visible during keyboard navigation
  useEffect(() => {
    if (selectedIndex === null || !scrollContainerRef.current) return;

    const container = scrollContainerRef.current;

    // ─── Behavioral Checks ──────────────────────────────────────────
    // 1. Is this widget even "visible" (not hidden in an inactive tab)?
    if (container.offsetParent === null) return;

    // 2. Is this an "internal" interaction?
    // We only scroll if either:
    // a) This specific container is focused (keyboard nav or just clicked)
    // b) The change came from clicking a row in this specific instance
    const isFocused =
      document.activeElement === container ||
      container.contains(document.activeElement);

    if (!isFocused) return;

    const rowTop = selectedIndex * ROW_HEIGHT;
    const rowBottom = rowTop + ROW_HEIGHT;
    const scrollTop = container.scrollTop;
    const viewHeight = container.clientHeight;

    if (rowBottom > scrollTop + viewHeight) {
      // Row is below viewport — scroll down just enough
      container.scrollTop = rowBottom - viewHeight;
    } else if (rowTop < scrollTop) {
      // Row is above viewport — scroll up just enough
      container.scrollTop = rowTop;
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
        <Button
          variant="outline"
          size="sm"
          className="h-7 gap-2 px-2.5 bg-background/50 hover:bg-background/80 border-border/50 text-xs font-medium"
          onClick={() => setListDialogOpen(true)}
        >
          <ListIcon className="w-3.5 h-3.5 text-primary" />
          <span className="truncate max-w-[120px]">
            {lists.find((l) => l.id === listId)?.name || "Select List"}
          </span>
          <ChevronDown className="w-3.5 h-3.5 text-muted-foreground" />
        </Button>

        <ListSelectionDialog
          open={listDialogOpen}
          onOpenChange={setListDialogOpen}
          selectedId={listId}
          onSelect={(id) => onSettingsChange({ listId: id })}
        />
        <button
          onClick={() => setCreateListOpen(true)}
          className="p-1 rounded-sm text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
          title="Create list"
        >
          <Plus className="w-3.5 h-3.5" />
        </button>

        <div className="flex-1" />

        {hasActiveFilters && (
          <button
            onClick={() => {
              const next = !filtersBypassed;
              setFiltersBypassed(next);
              onSettingsChange({ filtersBypassed: next });
            }}
            className={cn(
              "p-1 rounded-sm transition-colors",
              filtersBypassed
                ? "text-yellow-500 bg-yellow-500/10"
                : "text-muted-foreground hover:text-foreground hover:bg-muted",
            )}
            title={
              filtersBypassed
                ? "Show filtered results"
                : "Show all (bypass filters)"
            }
          >
            <FilterX className="w-3.5 h-3.5" />
          </button>
        )}

        {/* Options Menu */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button
              className="p-1 rounded-sm text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
              title="List options"
            >
              <MoreVertical className="w-3.5 h-3.5" />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-48">
            <DropdownMenuItem onClick={() => setListDialogOpen(true)}>
              <ListIcon className="w-3.5 h-3.5 mr-2" />
              Add symbol list
            </DropdownMenuItem>

            <DropdownMenuSeparator />
            {selectedList && (
              <DropdownMenuItem
                onClick={() => {
                  setRenameValue(selectedList.name);
                  setIsRenaming(true);
                }}
              >
                <Pencil className="w-3.5 h-3.5 mr-2" />
                Rename list
              </DropdownMenuItem>
            )}
            {isEditable && selectedList && (
              <DropdownMenuItem
                onClick={() => {
                  setSymbolsMutation.mutate(
                    { listId: selectedList.id, symbols: [] },
                    {
                      onSuccess: () => {
                        toast.success("List cleared");
                        refresh();
                      },
                    },
                  );
                }}
              >
                <Trash2 className="w-3.5 h-3.5 mr-2" />
                Clear list
              </DropdownMenuItem>
            )}
            {selectedList && (
              <DropdownMenuItem
                onClick={() => {
                  createListMutation.mutate(
                    {
                      name: `${selectedList.name} (copy)`,
                      type: selectedList.type as "simple" | "color" | "combo",
                      color: selectedList.color ?? undefined,
                    },
                    {
                      onSuccess: (newList) => {
                        // Copy symbols to the new list
                        setSymbolsMutation.mutate(
                          { listId: newList.id, symbols: selectedList.symbols },
                          {
                            onSuccess: () => {
                              toast.success(`Copied as "${newList.name}"`);
                              onSettingsChange({ listId: newList.id });
                            },
                          },
                        );
                      },
                    },
                  );
                }}
              >
                <Copy className="w-3.5 h-3.5 mr-2" />
                Make a copy
              </DropdownMenuItem>
            )}
            <DropdownMenuSeparator />
            <DropdownMenuItem
              onClick={() => {
                if (!selectedList) return;
                const symbols = selectedList.symbols
                  .filter((s) => !s.startsWith("###"))
                  .join(",");
                const blob = new Blob([symbols], { type: "text/csv" });
                const url = URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = url;
                a.download = `${selectedList.name}.csv`;
                a.click();
                URL.revokeObjectURL(url);
                toast.success("Downloaded CSV");
              }}
            >
              <Download className="w-3.5 h-3.5 mr-2" />
              Download CSV
            </DropdownMenuItem>
            {isEditable && (
              <DropdownMenuItem onClick={() => fileInputRef.current?.click()}>
                <Upload className="w-3.5 h-3.5 mr-2" />
                Upload CSV
              </DropdownMenuItem>
            )}
          </DropdownMenuContent>
        </DropdownMenu>
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv,.txt"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (!file || !selectedList) return;
            const reader = new FileReader();
            reader.onload = (ev) => {
              const text = ev.target?.result as string;
              const symbols = text
                .split(/[,\n\r]+/)
                .map((s) => s.trim())
                .filter(Boolean);
              if (symbols.length > 0) {
                const merged = [
                  ...new Set([...selectedList.symbols, ...symbols]),
                ];
                setSymbolsMutation.mutate(
                  { listId: selectedList.id, symbols: merged },
                  {
                    onSuccess: () => {
                      toast.success(`Added ${symbols.length} symbols`);
                      refresh();
                    },
                  },
                );
              }
            };
            reader.readAsText(file);
            e.target.value = "";
          }}
        />

        <button
          onClick={() => setEditorOpen(true)}
          className="p-1 rounded-sm text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
          title="Edit columns"
        >
          <Settings className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* Rename inline bar */}
      {isRenaming && selectedList && (
        <div className="border-b border-border bg-muted/40 px-3 h-8 flex items-center gap-2 shrink-0">
          <span className="text-[10px] text-muted-foreground uppercase tracking-wider">
            Rename:
          </span>
          <input
            autoFocus
            type="text"
            value={renameValue}
            onChange={(e) => setRenameValue(e.target.value)}
            onBlur={() => {
              if (
                renameValue.trim() &&
                renameValue.trim() !== selectedList.name
              ) {
                updateListMutation.mutate(
                  { id: selectedList.id, data: { name: renameValue.trim() } },
                  {
                    onSuccess: () => toast.success("List renamed"),
                  },
                );
              }
              setIsRenaming(false);
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter") (e.target as HTMLInputElement).blur();
              if (e.key === "Escape") setIsRenaming(false);
            }}
            className="flex-1 bg-transparent outline-none text-xs text-foreground"
          />
          <span className="text-[10px] text-muted-foreground">
            Enter to save · Esc to cancel
          </span>
        </div>
      )}

      <div
        ref={scrollContainerRef}
        className="flex-1 overflow-auto pb-10 outline-none focus-within:ring-1 focus-within:ring-primary/20 relative"
        tabIndex={0}
        onKeyDown={handleKeyDown}
      >
        {displayItems.length === 0 && !isLoading ? (
          <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
            No data
          </div>
        ) : (
          <table
            ref={tableRef}
            className="w-max text-xs table-fixed border-collapse"
          >
            <thead>
              <tr className="z-10">
                <th
                  style={{
                    width: getColWidth("ticker", 100),
                    minWidth: getColWidth("ticker", 100),
                    maxWidth: getColWidth("ticker", 100),
                  }}
                  className="text-left py-1.5 pr-1.5 font-medium text-muted-foreground transition-colors group/ticker overflow-hidden whitespace-nowrap sticky top-0 bg-card z-20 will-change-transform backface-hidden"
                >
                  <div className="flex items-center h-full">
                    <div className="w-4 shrink-0" />{" "}
                    {/* Spacer for flag + gap */}
                    <div
                      className="flex items-center h-full cursor-pointer hover:text-foreground truncate"
                      onClick={() => handleSort("ticker")}
                    >
                      Ticker
                      {renderSortIcon("ticker")}
                    </div>
                  </div>
                  <div className="absolute bottom-0 left-0 right-0 h-px bg-border" />
                  <div
                    onMouseDown={(e) =>
                      onResizeStart(e, "ticker", getColWidth("ticker", 100))
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
                        width: getColWidth(colId, 100),
                        minWidth: getColWidth(colId, 100),
                        maxWidth: getColWidth(colId, 100),
                      }}
                      className="text-right p-1.5 font-medium text-muted-foreground group/col overflow-hidden whitespace-nowrap sticky top-0 bg-card z-20 will-change-transform backface-hidden"
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
                      <div className="absolute bottom-0 left-0 right-0 h-px bg-border" />
                      <div
                        onMouseDown={(e) =>
                          onResizeStart(e, colId, getColWidth(colId, 100))
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
              {(() => {
                const virtualItems = rowVirtualizer.getVirtualItems();
                const paddingTop =
                  virtualItems.length > 0 ? virtualItems[0].start : 0;
                const paddingBottom =
                  virtualItems.length > 0
                    ? rowVirtualizer.getTotalSize() -
                      virtualItems[virtualItems.length - 1].end
                    : 0;

                return (
                  <>
                    {paddingTop > 0 && (
                      <tr>
                        <td
                          colSpan={visibleColumns.length + 1}
                          style={{ height: paddingTop, padding: 0, border: 0 }}
                        />
                      </tr>
                    )}
                    {virtualItems.map((virtualRow) => {
                      const item = displayItems[virtualRow.index];
                      if (!item) return null;

                      const originalIndex = item.tickerIndex;
                      const tickerEntry = deferredTickers[originalIndex];
                      if (!tickerEntry) return null;
                      return (
                        <ScreenerRow
                          key={tickerEntry.ticker}
                          row={tickerEntry}
                          originalIndex={originalIndex}
                          visualIndex={virtualRow.index}
                          isSelected={virtualRow.index === selectedIndex}
                          onSelect={handleSelect}
                          visibleColumns={visibleColumns}
                          columnMap={columnMap}
                          values={deferredValues}
                          isDark={isDark}
                          getColWidth={getColWidth}
                          screenerListId={listId}
                          onListModified={refresh}
                        />
                      );
                    })}
                    {paddingBottom > 0 && (
                      <tr>
                        <td
                          colSpan={visibleColumns.length + 1}
                          style={{
                            height: paddingBottom,
                            padding: 0,
                            border: 0,
                          }}
                        />
                      </tr>
                    )}
                  </>
                );
              })()}
            </tbody>
          </table>
        )}
      </div>

      <div className="absolute bottom-2 left-2 right-2 flex items-center justify-between pointer-events-none z-20">
        <ScreenerStatus
          filteredSymbols={tickers.length}
          totalSymbols={totalSymbols}
          lastUpdate={lastUpdate}
          isLoading={isLoading}
        />
        {sortConfig.key && (
          <button
            onClick={handleResort}
            className="pointer-events-auto flex items-center gap-1 bg-background/80 backdrop-blur-sm border border-border/50 rounded-sm px-2 py-0.5 text-xs font-mono text-muted-foreground hover:text-foreground hover:border-border transition-colors"
          >
            <RefreshCw className="w-3 h-3" />
            Resort
          </button>
        )}
      </div>

      <ColumnEditor
        open={editorOpen}
        onClose={() => setEditorOpen(false)}
        columns={columns}
        onColumnsChange={(cols) => onSettingsChange({ columns: cols })}
      />

      <CreateListDialog
        open={createListOpen}
        onClose={() => setCreateListOpen(false)}
        onCreated={(list) => onSettingsChange({ listId: list.id })}
      />
    </div>
  );
}
