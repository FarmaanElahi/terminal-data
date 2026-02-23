import { useAuthStore } from "@/stores/auth-store";
import { useWidget } from "@/hooks/use-widget";
import type { WidgetProps } from "@/types/layout";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ListIcon } from "lucide-react";

interface WatchlistSettings {
  listId: string | null;
}

export function WatchlistWidget({
  instanceId,
  settings,
  onSettingsChange,
}: WidgetProps) {
  const s = (settings ?? {}) as Partial<WatchlistSettings>;
  const lists = useAuthStore((st) => st.lists);
  const { broadcast } = useWidget(instanceId);

  const selectedList = lists?.find((l) => l.id === s.listId) ?? lists?.[0];

  const handleSymbolClick = (symbol: string) => {
    broadcast("context_change", { symbol });
  };

  return (
    <div className="flex flex-col h-full">
      {/* List selector */}
      <div className="flex items-center gap-2 p-2 border-b border-border shrink-0">
        <Select
          value={s.listId ?? selectedList?.id ?? ""}
          onValueChange={(v) => onSettingsChange({ listId: v })}
        >
          <SelectTrigger className="h-7 w-full text-xs">
            <SelectValue placeholder="Select watchlist" />
          </SelectTrigger>
          <SelectContent>
            {lists?.map((l) => (
              <SelectItem key={l.id} value={l.id}>
                {l.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Symbol list */}
      <div className="flex-1 overflow-auto">
        {!selectedList ? (
          <div className="flex flex-col items-center justify-center h-full text-muted-foreground gap-2">
            <ListIcon className="w-8 h-8" />
            <span className="text-sm">No watchlist selected</span>
          </div>
        ) : !selectedList.symbols || selectedList.symbols.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-muted-foreground gap-2">
            <span className="text-sm">Empty watchlist</span>
          </div>
        ) : (
          <div className="divide-y divide-border/50">
            {(selectedList.symbols ?? []).map((ticker: string) => (
              <button
                key={ticker}
                onClick={() => handleSymbolClick(ticker)}
                className="w-full flex items-center justify-between px-3 py-2 hover:bg-muted/30 transition-colors text-left"
              >
                <span className="text-xs font-medium">{ticker}</span>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
