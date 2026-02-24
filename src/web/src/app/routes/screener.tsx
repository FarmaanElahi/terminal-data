import { useState } from "react";
import { useAuthStore } from "@/stores/auth-store";
import { useScreener } from "@/hooks/use-screener";
import { ScreenerTable } from "@/components/screener/screener-table";
import { ScreenerToolbar } from "@/components/screener/screener-toolbar";
import { ScreenerStatus } from "@/components/screener/screener-status";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export function ScreenerPage() {
  const [selectedListId, setSelectedListId] = useState<string | null>(null);
  const [selectedColumnSetId, setSelectedColumnSetId] = useState<string | null>(
    null,
  );

  // Read from boot data — already loaded on auth
  const lists = useAuthStore((s) => s.lists);
  const columnSets = useAuthStore((s) => s.columnSets);

  // Auto-select first available
  const listId = selectedListId ?? lists?.[0]?.id ?? null;
  const columnSetId = selectedColumnSetId ?? columnSets?.[0]?.id ?? null;

  // Get column definitions for the selected column set
  const selectedColumnSet = columnSets?.find((cs) => cs.id === columnSetId);

  // Screener session
  const { tickers, values, isLoading, lastUpdate, totalSymbols } = useScreener(
    "screener-page",
    listId,
    selectedColumnSet?.columns || null,
  );

  return (
    <div className="flex flex-col h-full relative">
      {/* Header bar */}
      <div className="border-b border-border px-4 py-3 flex items-center gap-4 bg-card/30 shrink-0">
        <div className="flex items-center gap-2">
          <svg
            className="w-5 h-5 text-primary"
            fill="none"
            viewBox="0 0 24 24"
            strokeWidth={1.5}
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M3.375 19.5h17.25m-17.25 0a1.125 1.125 0 01-1.125-1.125M3.375 19.5h7.5c.621 0 1.125-.504 1.125-1.125m-9.75 0V5.625m0 12.75v-1.5c0-.621.504-1.125 1.125-1.125m18.375 2.625V5.625m0 12.75c0 .621-.504 1.125-1.125 1.125m1.125-1.125v-1.5c0-.621-.504-1.125-1.125-1.125m0 3.75h-7.5A1.125 1.125 0 0112 18.375m9.75-12.75c0-.621-.504-1.125-1.125-1.125H3.375c-.621 0-1.125.504-1.125 1.125m19.5 0v1.5c0 .621-.504 1.125-1.125 1.125M2.25 5.625v1.5c0 .621.504 1.125 1.125 1.125m0 0h17.25m-17.25 0h7.5c.621 0 1.125.504 1.125 1.125M3.375 8.25c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125m17.25-3.75h-7.5c-.621 0-1.125.504-1.125 1.125m8.625-1.125c.621 0 1.125.504 1.125 1.125v1.5c0 .621-.504 1.125-1.125 1.125m-17.25 0h7.5m-7.5 0c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125M12 10.875v-1.5m0 1.5c0 .621-.504 1.125-1.125 1.125M12 10.875c0 .621.504 1.125 1.125 1.125m-2.25 0c.621 0 1.125.504 1.125 1.125M10.875 12c-.621 0-1.125.504-1.125 1.125M12 12c.621 0 1.125.504 1.125 1.125m0 0v1.5c0 .621-.504 1.125-1.125 1.125m0-2.625c.621 0 1.125.504 1.125 1.125"
            />
          </svg>
          <h1 className="text-lg font-semibold">Screener</h1>
        </div>

        {/* List selector */}
        <Select value={listId ?? ""} onValueChange={setSelectedListId}>
          <SelectTrigger className="w-48 h-8 text-xs bg-background/50">
            <SelectValue placeholder="Select list..." />
          </SelectTrigger>
          <SelectContent>
            {lists?.map((list) => (
              <SelectItem key={list.id} value={list.id} className="text-xs">
                {list.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        {/* Column set selector */}
        <Select
          value={columnSetId ?? ""}
          onValueChange={setSelectedColumnSetId}
        >
          <SelectTrigger className="w-48 h-8 text-xs bg-background/50">
            <SelectValue placeholder="Select columns..." />
          </SelectTrigger>
          <SelectContent>
            {columnSets?.map((cs) => (
              <SelectItem key={cs.id} value={cs.id} className="text-xs">
                {cs.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Toolbar */}
      <ScreenerToolbar />

      {/* Table */}
      <div className="flex-1 overflow-hidden">
        {!listId || !columnSetId ? (
          <div className="flex items-center justify-center h-full">
            <div className="text-center space-y-3">
              <div className="w-16 h-16 rounded-full bg-muted flex items-center justify-center mx-auto">
                <svg
                  className="w-8 h-8 text-muted-foreground"
                  fill="none"
                  viewBox="0 0 24 24"
                  strokeWidth={1}
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M3.75 3v11.25A2.25 2.25 0 006 16.5h2.25M3.75 3h-1.5m1.5 0h16.5m0 0h1.5m-1.5 0v11.25A2.25 2.25 0 0118 16.5h-2.25m-7.5 0h7.5m-7.5 0l-1 3m8.5-3l1 3m0 0l.5 1.5m-.5-1.5h-9.5m0 0l-.5 1.5m.75-9l3-3 2.148 2.148A12.061 12.061 0 0116.5 7.605"
                  />
                </svg>
              </div>
              <div>
                <p className="text-sm font-medium text-muted-foreground">
                  Select a list and column set
                </p>
                <p className="text-xs text-muted-foreground/60">
                  to start the screener
                </p>
              </div>
            </div>
          </div>
        ) : (
          <ScreenerTable
            tickers={tickers}
            values={values}
            columns={selectedColumnSet?.columns ?? []}
            isLoading={isLoading}
          />
        )}
      </div>

      {/* Status bar */}
      <ScreenerStatus
        filteredSymbols={tickers.length}
        totalSymbols={totalSymbols}
        lastUpdate={lastUpdate}
        isLoading={isLoading}
      />
    </div>
  );
}
