import { useAuthStore } from "@/stores/auth-store";
import { useScreener } from "@/hooks/use-screener";
import type { WidgetProps } from "@/types/layout";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export function ScreenerWidget({ settings, onSettingsChange }: WidgetProps) {
  const s = (settings ?? {}) as Record<string, unknown>;
  const lists = useAuthStore((st) => st.lists);
  const columnSets = useAuthStore((st) => st.columnSets);

  const listId = (s.listId as string) ?? lists?.[0]?.id ?? null;
  const columnSetId = (s.columnSetId as string) ?? columnSets?.[0]?.id ?? null;

  const { tickers, values, isLoading } = useScreener(listId, columnSetId);

  return (
    <div className="flex flex-col h-full">
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

        {isLoading && (
          <span className="text-xs text-muted-foreground animate-pulse">
            Loading...
          </span>
        )}
      </div>

      <div className="flex-1 overflow-auto">
        {tickers.length === 0 && !isLoading ? (
          <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
            No data
          </div>
        ) : (
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-border sticky top-0 bg-card">
                <th className="text-left p-1.5 font-medium text-muted-foreground">
                  Ticker
                </th>
                {Object.keys(values).map((col) => (
                  <th
                    key={col}
                    className="text-right p-1.5 font-medium text-muted-foreground"
                  >
                    {col}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {tickers.map((row, i) => (
                <tr
                  key={row.ticker}
                  className="border-b border-border/50 hover:bg-muted/30 transition-colors"
                >
                  <td className="p-1.5 font-medium text-foreground">
                    {row.ticker}
                  </td>
                  {Object.entries(values).map(([col, vals]) => (
                    <td key={col} className="p-1.5 text-right tabular-nums">
                      {vals[i] != null ? String(vals[i]) : "—"}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
