import { useState } from "react";
import { useAuthStore } from "@/stores/auth-store";
import { useWidget } from "@/hooks/use-widget";
import type { WidgetProps } from "@/types/layout";
import { cn } from "@/lib/utils";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ListIcon, Plus } from "lucide-react";
import { CreateListDialog } from "./create-list-dialog";

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
  const { setChannelSymbol, channelContext } = useWidget(instanceId);
  const [createListOpen, setCreateListOpen] = useState(false);

  const selectedList = lists?.find((l) => l.id === s.listId) ?? lists?.[0];

  const handleSymbolClick = (symbol: string) => {
    setChannelSymbol(symbol);
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
        <button
          onClick={() => setCreateListOpen(true)}
          className="p-1 rounded-sm text-muted-foreground hover:text-foreground hover:bg-muted transition-colors shrink-0"
          title="Create list"
        >
          <Plus className="w-3.5 h-3.5" />
        </button>
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
            {(selectedList.symbols ?? []).map((ticker: string) => {
              const isActive = channelContext?.symbol === ticker;
              return (
                <button
                  key={ticker}
                  onClick={() => handleSymbolClick(ticker)}
                  className={cn(
                    "w-full flex items-center justify-between px-3 h-6 hover:bg-muted/30 transition-colors text-left",
                    isActive && "bg-primary/10 border-l-2 border-primary",
                  )}
                >
                  <span
                    className={cn(
                      "text-xs font-mono font-medium",
                      isActive ? "text-primary" : "text-foreground",
                    )}
                  >
                    {ticker}
                  </span>
                </button>
              );
            })}
          </div>
        )}
      </div>

      <CreateListDialog
        open={createListOpen}
        onClose={() => setCreateListOpen(false)}
        onCreated={(list) => onSettingsChange({ listId: list.id })}
      />
    </div>
  );
}
