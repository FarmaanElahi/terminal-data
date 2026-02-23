import { useState } from "react";
import { useLayoutStore } from "@/stores/layout-store";
import { Plus, Copy, Trash2, Pencil } from "lucide-react";

export function LayoutTabsBar() {
  const layouts = useLayoutStore((s) => s.layouts);
  const activeLayoutId = useLayoutStore((s) => s.activeLayoutId);
  const {
    switchLayout,
    createLayout,
    renameLayout,
    duplicateLayout,
    deleteLayout,
  } = useLayoutStore();

  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");

  const startEditing = (id: string, name: string) => {
    setEditingId(id);
    setEditValue(name);
  };

  const commitEdit = () => {
    if (editingId && editValue.trim()) {
      renameLayout(editingId, editValue.trim());
    }
    setEditingId(null);
  };

  return (
    <div className="flex items-center h-7 bg-muted/30 border-t border-border px-1 gap-0.5 shrink-0">
      {layouts.map((layout) => (
        <div key={layout.id} className="group flex items-center">
          {editingId === layout.id ? (
            <input
              className="h-5 px-2 text-xs bg-card border border-primary rounded-sm outline-none w-24"
              value={editValue}
              onChange={(e) => setEditValue(e.target.value)}
              onBlur={commitEdit}
              onKeyDown={(e) => {
                if (e.key === "Enter") commitEdit();
                if (e.key === "Escape") setEditingId(null);
              }}
              autoFocus
            />
          ) : (
            <button
              onClick={() => switchLayout(layout.id)}
              onDoubleClick={() => startEditing(layout.id, layout.name)}
              className={`
                h-5 px-3 text-xs rounded-sm transition-colors
                ${
                  layout.id === activeLayoutId
                    ? "bg-card text-foreground border border-border"
                    : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
                }
              `}
            >
              {layout.name}
            </button>
          )}

          {/* Context actions on hover */}
          {layout.id === activeLayoutId && (
            <div className="hidden group-hover:flex items-center gap-0.5 ml-0.5">
              <button
                onClick={() => startEditing(layout.id, layout.name)}
                className="p-0.5 rounded-sm text-muted-foreground hover:text-foreground"
                title="Rename"
              >
                <Pencil className="w-2.5 h-2.5" />
              </button>
              <button
                onClick={() => duplicateLayout(layout.id)}
                className="p-0.5 rounded-sm text-muted-foreground hover:text-foreground"
                title="Duplicate"
              >
                <Copy className="w-2.5 h-2.5" />
              </button>
              {layouts.length > 1 && (
                <button
                  onClick={() => deleteLayout(layout.id)}
                  className="p-0.5 rounded-sm text-muted-foreground hover:text-destructive"
                  title="Delete"
                >
                  <Trash2 className="w-2.5 h-2.5" />
                </button>
              )}
            </div>
          )}
        </div>
      ))}

      <button
        onClick={createLayout}
        className="h-5 px-1.5 text-muted-foreground hover:text-foreground rounded-sm hover:bg-muted/50 transition-colors"
        title="New Layout"
      >
        <Plus className="w-3 h-3" />
      </button>
    </div>
  );
}
