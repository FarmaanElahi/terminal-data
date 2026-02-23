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
  const visibleColumns = useMemo(
    () => columns.filter((c) => c.visible !== false),
    [columns],
  );

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

  return (
    <div className="h-full overflow-auto scrollbar-thin">
      <Table>
        <TableHeader className="sticky top-0 z-10 bg-card">
          <TableRow className="hover:bg-transparent border-b border-border">
            <TableHead className="w-32 text-xs font-semibold h-8 sticky left-0 bg-card z-20">
              Ticker
            </TableHead>
            <TableHead className="w-48 text-xs font-semibold h-8">
              Name
            </TableHead>
            {visibleColumns.map((col) => (
              <TableHead
                key={col.id}
                className="text-xs font-semibold h-8 text-right min-w-[80px] cursor-pointer hover:text-foreground transition-colors"
              >
                {col.name}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {tickers.map((ticker, rowIndex) => (
            <ScreenerRow
              key={ticker.ticker}
              ticker={ticker}
              rowIndex={rowIndex}
              columns={visibleColumns}
              values={values}
            />
          ))}
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
  return (
    <TableRow className="hover:bg-muted/30 border-b border-border/50 transition-colors">
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
