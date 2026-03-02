import { useEffect, useMemo, useRef } from "react";
import { toast } from "sonner";
import { useAddSymbolMutation, useListsQuery } from "@/queries/use-lists";
import { useLayoutStore } from "@/stores/layout-store";
import type { List } from "@/types/models";

export function useSaveToWatchlist() {
  const { mutate } = useAddSymbolMutation();
  const { data: lists = [] } = useListsQuery();
  const globalContext = useLayoutStore((s) => s.globalContext);

  const symbolRef = useRef<string | undefined>(undefined);
  const listRef = useRef<List | undefined>(undefined);
  const mutateRef = useRef(mutate);

  const targetList = useMemo(() => {
    const lastSavedId = localStorage.getItem("last_saved_watchlist_id");
    return lists.find((l) => l.id === lastSavedId && l.type !== "system") ?? null;
  }, [lists]);

  symbolRef.current = globalContext.symbol;
  listRef.current = targetList ?? undefined;
  mutateRef.current = mutate;

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (!(e.ctrlKey || e.metaKey) || e.key !== "w") return;

      const el = document.activeElement;
      if (el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement) return;
      if ((el as HTMLElement)?.getAttribute?.("contenteditable")) return;

      e.preventDefault();

      const symbol = symbolRef.current;
      if (!symbol) return;

      const list = listRef.current;
      if (!list) return;

      if (list.symbols.includes(symbol)) {
        toast.info(`${symbol} already in ${list.name}`);
        return;
      }

      mutateRef.current(
        { listId: list.id, ticker: symbol },
        {
          onSuccess: () => {
            toast.success(`Saved ${symbol} to ${list.name}`);
            localStorage.setItem("last_saved_watchlist_id", list.id);
          },
          onError: () => toast.error("Failed to save symbol"),
        },
      );
    };

    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);
}
