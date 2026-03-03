import { useState } from "react";
import { getAllWidgets } from "@/lib/widget-registry";
import { useLayoutStore } from "@/stores/layout-store";
import {
  X,
  TableProperties,
  LineChart,
  List,
  Users,
  Link,
  LayoutGrid,
  Search,
} from "lucide-react";

const WIDGET_ICONS: Record<string, React.ElementType> = {
  screener: TableProperties,
  chart: LineChart,
  watchlist: List,
  community: Users,
  broker: Link,
};

function getWidgetIcon(type: string): React.ElementType {
  return WIDGET_ICONS[type] ?? LayoutGrid;
}

interface AddWidgetDialogProps {
  open: boolean;
  onClose: () => void;
  /** If provided, add as tab to this pane. Otherwise split from root. */
  targetPaneId?: string;
}

export function AddWidgetDialog({
  open,
  onClose,
  targetPaneId,
}: AddWidgetDialogProps) {
  const { addTab, splitPane } = useLayoutStore();
  const [query, setQuery] = useState("");

  if (!open) return null;

  const allWidgets = getAllWidgets();
  const widgets = query.trim()
    ? allWidgets.filter(
        (w) =>
          w.title.toLowerCase().includes(query.toLowerCase()) ||
          w.type.toLowerCase().includes(query.toLowerCase()),
      )
    : allWidgets;

  const handleSelect = (widgetType: string) => {
    if (targetPaneId) {
      addTab(targetPaneId, widgetType);
    } else {
      const layout = useLayoutStore.getState().getActiveLayout();
      const findFirstPane = (node: {
        type: string;
        id: string;
        children?: { type: string; id: string; children?: unknown[] }[];
      }): string | null => {
        if (node.type === "pane") return node.id;
        if ("children" in node && Array.isArray(node.children)) {
          for (const child of node.children) {
            const found = findFirstPane(child as typeof node);
            if (found) return found;
          }
        }
        return null;
      };
      const paneId = findFirstPane(layout.root);
      if (paneId) splitPane(paneId, "vertical", widgetType);
    }
    setQuery("");
    onClose();
  };

  const handleClose = () => {
    setQuery("");
    onClose();
  };

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60"
      onClick={handleClose}
    >
      <div
        className="bg-card border border-border shadow-2xl w-96 max-h-[400px] overflow-hidden flex flex-col rounded-sm"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center gap-2 px-3 py-2 border-b border-border shrink-0">
          <Search className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
          <input
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search widgets..."
            className="flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground font-mono"
            onKeyDown={(e) => {
              if (e.key === "Escape") handleClose();
              if (e.key === "Enter" && widgets.length === 1) {
                handleSelect(widgets[0].type);
              }
            }}
          />
          <button
            onClick={handleClose}
            className="text-muted-foreground hover:text-foreground shrink-0"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Widget list */}
        <div className="overflow-y-auto flex-1 p-1">
          {widgets.length === 0 ? (
            <p className="text-sm text-muted-foreground p-3 font-mono text-center">
              No widgets match "{query}"
            </p>
          ) : (
            widgets.map((def) => {
              const Icon = getWidgetIcon(def.type);
              return (
                <button
                  key={def.type}
                  onClick={() => handleSelect(def.type)}
                  className="w-full flex items-center gap-3 px-3 py-2.5 rounded-sm hover:bg-primary/10 hover:text-primary transition-colors text-left group"
                >
                  <div className="w-7 h-7 rounded-sm bg-muted group-hover:bg-primary/20 flex items-center justify-center text-muted-foreground group-hover:text-primary transition-colors shrink-0">
                    <Icon className="w-3.5 h-3.5" />
                  </div>
                  <div className="min-w-0">
                    <div className="text-sm font-medium leading-none mb-0.5">
                      {def.title}
                    </div>
                    <div className="text-xs text-muted-foreground font-mono group-hover:text-primary/70">
                      {def.type}
                    </div>
                  </div>
                </button>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}
