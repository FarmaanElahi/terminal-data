import { useState, useCallback, useEffect } from "react";
import { columnsApi } from "@/lib/api";
import { useAuthStore } from "@/stores/auth-store";
import type { ColumnSet, ColumnDef, FilterState } from "@/types/models";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { FormulaEditor } from "./formula-editor";
import { Eye, EyeOff, X, Plus, Filter } from "lucide-react";

interface ColumnEditorProps {
  open: boolean;
  onClose: () => void;
  columnSet: ColumnSet;
}

const TIMEFRAMES = [
  { value: "D", label: "D" },
  { value: "W", label: "W" },
  { value: "M", label: "M" },
  { value: "Y", label: "Y" },
];

function makeColumnId(): string {
  return `col_${crypto.randomUUID().slice(0, 8)}`;
}

function newColumn(): ColumnDef {
  return {
    id: makeColumnId(),
    name: "New Column",
    type: "value",
    formula: "close",
    timeframe: "D",
    bar_ago: 0,
    visible: true,
    condition_id: null,
    filter: "off",
  };
}

const FILTER_CYCLE: Record<FilterState, FilterState> = {
  off: "active",
  active: "inactive",
  inactive: "off",
};

export function ColumnEditor({ open, onClose, columnSet }: ColumnEditorProps) {
  const [columns, setColumns] = useState<ColumnDef[]>([]);
  const [isSaving, setIsSaving] = useState(false);
  const [hasChanges, setHasChanges] = useState(false);
  const [editingIdx, setEditingIdx] = useState<number | null>(null);

  useEffect(() => {
    if (open) {
      setColumns([...columnSet.columns]);
      setHasChanges(false);
      setEditingIdx(null);
    }
  }, [open, columnSet.columns]);

  const updateColumn = useCallback(
    (index: number, patch: Partial<ColumnDef>) => {
      setColumns((prev) => {
        const next = [...prev];
        next[index] = { ...next[index], ...patch };
        return next;
      });
      setHasChanges(true);
    },
    [],
  );

  const addColumn = useCallback(() => {
    const col = newColumn();
    setColumns((prev) => [...prev, col]);
    setEditingIdx(columns.length);
    setHasChanges(true);
  }, [columns.length]);

  const removeColumn = useCallback((index: number) => {
    setColumns((prev) => prev.filter((_, i) => i !== index));
    setEditingIdx(null);
    setHasChanges(true);
  }, []);

  const save = useCallback(async () => {
    setIsSaving(true);
    try {
      const { data } = await columnsApi.update(columnSet.id, {
        columns: columns.map((c) => ({
          ...c,
          condition_id: c.condition_id ?? undefined,
        })),
      });
      useAuthStore.setState((state) => ({
        columnSets: state.columnSets.map((cs) =>
          cs.id === columnSet.id ? data : cs,
        ),
      }));
      setHasChanges(false);
      onClose();
    } catch (err) {
      console.error("Failed to save columns:", err);
    } finally {
      setIsSaving(false);
    }
  }, [columns, columnSet.id, onClose]);

  return (
    <Dialog
      open={open}
      onOpenChange={(isOpen) => {
        if (!isOpen) onClose();
      }}
    >
      <DialogContent
        showCloseButton={false}
        className="sm:max-w-2xl p-0 gap-0 overflow-hidden"
      >
        {/* ─── Header (drag handle) ──────────────────────────── */}
        <DialogHeader className="px-4 py-2.5 border-b border-border">
          <div className="flex items-center justify-between">
            <DialogTitle className="text-sm">
              Edit Columns & Filters
            </DialogTitle>
            <button
              onClick={onClose}
              className="text-muted-foreground hover:text-foreground p-1 rounded-sm hover:bg-muted transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
          <DialogDescription className="sr-only">
            Edit column visibility, formulas, filters, and timeframes
          </DialogDescription>
        </DialogHeader>

        {/* ─── Table Header ──────────────────────────────────── */}
        <div className="grid grid-cols-[36px_1fr_1fr_56px_50px_32px] items-center px-2 py-1.5 border-b border-border bg-muted/30 text-[10px] uppercase tracking-wider text-muted-foreground font-medium">
          <div className="text-center">Vis</div>
          <div>Column Name</div>
          <div>Formula</div>
          <div className="text-center">Filter</div>
          <div className="text-center">Time</div>
          <div />
        </div>

        {/* ─── Column Rows ───────────────────────────────────── */}
        <div className="overflow-auto max-h-[60vh]">
          {columns.map((col, i) => (
            <div
              key={col.id}
              className={`grid grid-cols-[36px_1fr_1fr_56px_50px_32px] items-center px-2 border-b border-border/50 transition-colors ${
                editingIdx === i ? "bg-muted/40" : "hover:bg-muted/20"
              }`}
              style={{ minHeight: "36px" }}
            >
              {/* Visible */}
              <div className="flex justify-center">
                <button
                  onClick={() => updateColumn(i, { visible: !col.visible })}
                  className={`p-1 rounded-sm transition-colors ${
                    col.visible
                      ? "text-foreground hover:text-muted-foreground"
                      : "text-muted-foreground/30 hover:text-muted-foreground"
                  }`}
                  title={col.visible ? "Hide" : "Show"}
                >
                  {col.visible ? (
                    <Eye className="w-3.5 h-3.5" />
                  ) : (
                    <EyeOff className="w-3.5 h-3.5" />
                  )}
                </button>
              </div>

              {/* Column Name */}
              <div className="pr-1.5 py-1">
                {editingIdx === i ? (
                  <Input
                    value={col.name}
                    onChange={(e) => updateColumn(i, { name: e.target.value })}
                    onBlur={() => setEditingIdx(null)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") setEditingIdx(null);
                    }}
                    className="h-7 text-xs"
                    autoFocus
                  />
                ) : (
                  <button
                    onClick={() => setEditingIdx(i)}
                    className="text-xs text-foreground hover:text-foreground/80 truncate text-left w-full py-0.5"
                    title="Click to edit name"
                  >
                    {col.name}
                  </button>
                )}
              </div>

              {/* Formula */}
              <div className="pr-1.5 py-1">
                <FormulaEditor
                  value={col.formula ?? ""}
                  onChange={(v) => updateColumn(i, { formula: v })}
                  height={26}
                />
              </div>

              {/* Filter */}
              <div className="flex justify-center">
                {col.condition_id ? (
                  <button
                    onClick={() =>
                      updateColumn(i, {
                        filter: FILTER_CYCLE[col.filter ?? "off"],
                      })
                    }
                    className={`p-1 rounded-sm transition-colors ${
                      col.filter === "active"
                        ? "text-blue-400 bg-blue-500/15"
                        : col.filter === "inactive"
                          ? "text-red-400 bg-red-500/10"
                          : "text-muted-foreground/40 hover:text-muted-foreground"
                    }`}
                    title={`Filter: ${col.filter ?? "off"}`}
                  >
                    <Filter className="w-3.5 h-3.5" />
                  </button>
                ) : (
                  <span className="text-muted-foreground/20 p-1">
                    <Filter className="w-3.5 h-3.5" />
                  </span>
                )}
              </div>

              {/* Timeframe */}
              <div className="flex justify-center">
                <Select
                  value={col.timeframe ?? "D"}
                  onValueChange={(v) =>
                    updateColumn(i, { timeframe: v as ColumnDef["timeframe"] })
                  }
                >
                  <SelectTrigger className="h-6 w-11 text-[10px] px-1.5 border-0 bg-transparent hover:bg-muted">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {TIMEFRAMES.map((tf) => (
                      <SelectItem key={tf.value} value={tf.value}>
                        {tf.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Delete */}
              <div className="flex justify-center">
                <button
                  onClick={() => removeColumn(i)}
                  className="p-1 rounded-sm text-muted-foreground/40 hover:text-red-500 hover:bg-red-500/10 transition-colors"
                  title="Remove"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          ))}

          {columns.length === 0 && (
            <div className="flex items-center justify-center py-8 text-muted-foreground text-xs">
              No columns
            </div>
          )}
        </div>

        {/* ─── Footer ────────────────────────────────────────── */}
        <div className="flex items-center gap-2 px-3 py-2.5 border-t border-border">
          <Button
            variant="ghost"
            size="sm"
            onClick={addColumn}
            className="text-xs h-7"
          >
            <Plus className="w-3 h-3 mr-1" />
            Add Column
          </Button>

          <div className="flex-1" />

          {hasChanges ? (
            <>
              <Button
                variant="ghost"
                size="sm"
                onClick={onClose}
                className="text-xs h-7"
              >
                Cancel
              </Button>
              <Button
                size="sm"
                onClick={save}
                disabled={isSaving}
                className="text-xs h-7"
              >
                {isSaving ? "Saving..." : "Save"}
              </Button>
            </>
          ) : (
            <Button
              variant="outline"
              size="sm"
              onClick={onClose}
              className="text-xs h-7"
            >
              Close
            </Button>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
