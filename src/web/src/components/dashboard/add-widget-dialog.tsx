import { getAllWidgets } from "@/lib/widget-registry";
import { useLayoutStore } from "@/stores/layout-store";
import { X, Plus } from "lucide-react";

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

  if (!open) return null;

  const widgets = getAllWidgets();

  const handleSelect = (widgetType: string) => {
    if (targetPaneId) {
      addTab(targetPaneId, widgetType);
    } else {
      const layout = useLayoutStore.getState().getActiveLayout();
      // Find first pane in the tree to split
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
    onClose();
  };

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50"
      onClick={onClose}
    >
      <div
        className="bg-card border border-border rounded-lg shadow-2xl w-80 max-h-96 overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between p-3 border-b border-border">
          <h3 className="text-sm font-medium">Add Widget</h3>
          <button
            onClick={onClose}
            className="text-muted-foreground hover:text-foreground"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="p-2 space-y-1 overflow-y-auto max-h-72">
          {widgets.length === 0 ? (
            <p className="text-sm text-muted-foreground p-2">
              No widgets registered
            </p>
          ) : (
            widgets.map((def) => (
              <button
                key={def.type}
                onClick={() => handleSelect(def.type)}
                className="w-full flex items-center gap-3 p-2 rounded-md hover:bg-muted/50 transition-colors text-left"
              >
                <div className="w-8 h-8 rounded-md bg-muted flex items-center justify-center text-muted-foreground">
                  <Plus className="w-4 h-4" />
                </div>
                <div>
                  <div className="text-sm font-medium">{def.title}</div>
                  <div className="text-xs text-muted-foreground">
                    {def.type}
                  </div>
                </div>
              </button>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
