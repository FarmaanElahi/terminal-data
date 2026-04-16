import { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { useListsQuery, useDeleteListMutation } from "@/queries/use-lists";
import { listsApi } from "@/lib/api";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import {
  ContextMenu,
  ContextMenuContent,
  ContextMenuItem,
  ContextMenuSeparator,
  ContextMenuTrigger,
} from "@/components/ui/context-menu";
import type { List } from "@/types/models";

interface AppSidebarProps {
  open: boolean;
}

export function AppSidebar({ open }: AppSidebarProps) {
  const navigate = useNavigate();
  const { data: lists = [] } = useListsQuery();
  const deleteList = useDeleteListMutation();

  // Map of list id → list, used to compute combo symbol counts on the fly.
  // Combo lists don't own symbols; their count is the union of their members.
  // Because member lists mutate via the same QUERY_KEYS.lists cache, this
  // derivation updates automatically when a member is added/removed.
  const listsById = useMemo(() => {
    const m = new Map<string, List>();
    for (const l of lists) m.set(l.id, l);
    return m;
  }, [lists]);

  const getSymbolCount = (list: List): number => {
    if (list.type !== "combo") return list.symbols.length;
    const seen = new Set<string>();
    for (const id of list.source_list_ids ?? []) {
      const member = listsById.get(id);
      if (!member) continue;
      for (const s of member.symbols) {
        if (!s.startsWith("###")) seen.add(s);
      }
    }
    return seen.size;
  };

  if (!open) return null;

  async function handleCopyTickers(list: List) {
    try {
      // Refetch to resolve combo members + strip "### section" placeholders
      // server-side — listsApi.get already returns aggregated symbols.
      const { data } = await listsApi.get(list.id);
      const symbols = (data.symbols ?? []).filter((s) => !s.startsWith("###"));
      if (symbols.length === 0) {
        toast.info(`"${list.name}" has no tickers to copy`);
        return;
      }
      await navigator.clipboard.writeText(symbols.join(","));
      const preview = symbols.slice(0, 5).join(", ");
      const overflow = symbols.length > 5 ? ` +${symbols.length - 5} more` : "";
      toast.success(`Copied ${symbols.length} ticker${symbols.length !== 1 ? "s" : ""}`, {
        description: preview + overflow,
      });
    } catch (err) {
      console.error("Failed to copy tickers", err);
      toast.error("Failed to copy tickers");
    }
  }

  async function handleDelete(list: List) {
    if (!window.confirm(`Delete list "${list.name}"? This cannot be undone.`)) {
      return;
    }
    try {
      await deleteList.mutateAsync(list.id);
      toast.success(`Deleted "${list.name}"`);
    } catch (err) {
      console.error("Failed to delete list", err);
      toast.error("Failed to delete list");
    }
  }

  return (
    <aside className="w-56 border-r border-border bg-sidebar shrink-0 flex flex-col">
      {/* Header */}
      <div className="px-3 py-3 flex items-center justify-between">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Watchlists
        </h2>
        <Button
          variant="ghost"
          size="icon"
          className="h-6 w-6 text-muted-foreground hover:text-foreground"
        >
          <svg
            className="w-3.5 h-3.5"
            fill="none"
            viewBox="0 0 24 24"
            strokeWidth={2}
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M12 4.5v15m7.5-7.5h-15"
            />
          </svg>
        </Button>
      </div>

      <Separator />

      {/* List items */}
      <ScrollArea className="flex-1">
        <div className="px-2 py-2 space-y-0.5">
          {lists?.map((list) => {
            const isSystem = list.id.startsWith("sys:");
            const isColor = list.type === "color";
            const canDelete = !isSystem && !isColor;
            return (
              <ContextMenu key={list.id}>
                <ContextMenuTrigger asChild>
                  <button
                    className="w-full flex items-center gap-2 px-2 py-1.5 rounded-md text-sm text-sidebar-foreground hover:bg-sidebar-accent transition-colors text-left"
                    onClick={() => navigate(`/lists/${list.id}`)}
                  >
                    {/* Color dot */}
                    <span
                      className="w-2 h-2 rounded-full shrink-0"
                      style={{
                        backgroundColor: list.color ?? "var(--primary)",
                      }}
                    />
                    <span className="truncate flex-1">{list.name}</span>
                    <Badge variant="secondary" className="text-[10px] h-4 px-1">
                      {getSymbolCount(list)}
                    </Badge>
                  </button>
                </ContextMenuTrigger>
                <ContextMenuContent className="w-44">
                  <ContextMenuItem onSelect={() => handleCopyTickers(list)}>
                    Copy tickers
                  </ContextMenuItem>
                  {canDelete && (
                    <>
                      <ContextMenuSeparator />
                      <ContextMenuItem
                        variant="destructive"
                        onSelect={() => handleDelete(list)}
                      >
                        Delete list
                      </ContextMenuItem>
                    </>
                  )}
                </ContextMenuContent>
              </ContextMenu>
            );
          })}

          {!lists?.length && (
            <div className="px-2 py-8 text-center">
              <p className="text-xs text-muted-foreground">No watchlists yet</p>
              <p className="text-xs text-muted-foreground/60 mt-1">
                Create one to get started
              </p>
            </div>
          )}
        </div>
      </ScrollArea>

      {/* Quick actions */}
      <div className="border-t border-sidebar-border p-2">
        <Button
          variant="ghost"
          size="sm"
          className="w-full justify-start text-xs text-muted-foreground h-7"
          onClick={() => navigate("/screener")}
        >
          <svg
            className="w-3.5 h-3.5 mr-2"
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
          Screener
        </Button>
      </div>
    </aside>
  );
}
