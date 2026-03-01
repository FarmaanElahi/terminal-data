import { useState, useCallback, useEffect } from "react";
import { useUpdateColumnSetMutation } from "@/queries/use-column-sets";
import type { ColumnSet, ColumnDef, FilterState } from "@/types/models";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ColumnPropertiesDialog } from "./column-properties-dialog";
import { Eye, EyeOff, X, Plus, Filter, ChevronRight } from "lucide-react";

// ─── Helpers ─────────────────────────────────────────────────────────

interface ColumnEditorProps {
  open: boolean;
  onClose: () => void;
  columnSet: ColumnSet;
}

function makeId(): string {
  return `col_${crypto.randomUUID().slice(0, 8)}`;
}

function newValueColumn(): ColumnDef {
  return {
    id: makeId(),
    name: "New Column",
    visible: true,
    type: "value",
    filter: "off",
    value_type: "formula",
    value_formula: "close",
    value_formula_tf: "D",
    value_formula_x_bar_ago: 0,
    value_formula_filter_enabled: false,
    value_formula_filter_op: "gt",
    value_formula_filter_params: [0],
    value_formula_filter_evaluate_on: "now",
    value_formula_refresh_interval: 0,
    display_column_width: 100,
    display_color: "#94a3b8",
  };
}

function newConditionColumn(): ColumnDef {
  return {
    id: makeId(),
    name: "New Condition",
    visible: true,
    type: "condition",
    filter: "off",
    conditions: [
      { formula: "C > C.1", evaluate_as: "true", evaluate_as_params: [] },
    ],
    conditions_logic: "and",
    condition_tf_mode: "fixed",
    conditions_tf: "D",
    condition_value_x_bar_ago: 0,
    display_column_width: 100,
    display_color: "#94a3b8",
  };
}

const FILTER_CYCLE: Record<FilterState, FilterState> = {
  off: "active",
  active: "inactive",
  inactive: "off",
};

// ─── Main Component ──────────────────────────────────────────────────

export function ColumnEditor({ open, onClose, columnSet }: ColumnEditorProps) {
  const [columns, setColumns] = useState<ColumnDef[]>([]);
  const [hasChanges, setHasChanges] = useState(false);
  const [editingColIdx, setEditingColIdx] = useState<number | null>(null);
  const updateColumnSet = useUpdateColumnSetMutation();

  useEffect(() => {
    if (open) {
      setColumns([...columnSet.columns]);
      setHasChanges(false);
      setEditingColIdx(null);
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

  const removeColumn = useCallback((index: number) => {
    setColumns((prev) => prev.filter((_, i) => i !== index));
    setHasChanges(true);
  }, []);

  const addColumn = useCallback(
    (type: "value" | "condition") => {
      const col = type === "value" ? newValueColumn() : newConditionColumn();
      setColumns((prev) => [...prev, col]);
      setHasChanges(true);
      setEditingColIdx(columns.length);
    },
    [columns.length],
  );

  const save = useCallback(async () => {
    try {
      await updateColumnSet.mutateAsync({
        id: columnSet.id,
        data: { columns: columns as unknown as ColumnDef[] },
      });
      setHasChanges(false);
      onClose();
    } catch (err) {
      console.error("Failed to save columns:", err);
    }
  }, [columns, columnSet.id, onClose, updateColumnSet]);

  return (
    <>
      <Dialog
        open={open}
        onOpenChange={(isOpen) => {
          if (!isOpen) onClose();
        }}
      >
        <DialogContent
          showCloseButton={false}
          className="sm:max-w-2xl p-0 gap-0 overflow-hidden flex flex-col max-h-[85vh]"
        >
          {/* ─── Header ────────────────────────────────────────── */}
          <DialogHeader className="px-5 py-3.5 border-b border-border shrink-0">
            <div className="flex items-center justify-between">
              <div>
                <DialogTitle className="text-sm font-semibold">
                  Edit Column Set: {columnSet.name}
                </DialogTitle>
                <DialogDescription className="text-xs mt-0.5">
                  Manage visibility, formulas, and screener filters
                </DialogDescription>
              </div>
              <button
                onClick={onClose}
                className="text-muted-foreground hover:text-foreground p-1 rounded-sm hover:bg-muted transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </DialogHeader>

          {/* ─── Table Header ──────────────────────────────────── */}
          <div className="grid grid-cols-[36px_1fr_60px_60px_32px] items-center px-3 py-2 border-b border-border bg-muted/30 text-xs uppercase tracking-wider text-muted-foreground font-semibold shrink-0">
            <div className="text-center">Vis</div>
            <div>Column Name / Source</div>
            <div className="text-center">Screener</div>
            <div className="text-center">Type</div>
            <div />
          </div>

          {/* ─── Column List ───────────────────────────────────── */}
          <div className="flex-1 overflow-auto bg-card/50">
            {columns.map((col, i) => (
              <div
                key={col.id}
                className="grid grid-cols-[36px_1fr_60px_60px_32px] items-center px-3 border-b border-border/50 group hover:bg-muted/30 transition-all cursor-pointer"
                style={{ minHeight: "44px" }}
                onClick={() => setEditingColIdx(i)}
              >
                {/* Visible Toggle */}
                <div
                  className="flex justify-center"
                  onClick={(e) => e.stopPropagation()}
                >
                  <button
                    onClick={() => updateColumn(i, { visible: !col.visible })}
                    className={`p-1 rounded-sm transition-colors ${
                      col.visible
                        ? "text-primary hover:text-primary/70"
                        : "text-muted-foreground/30 hover:text-muted-foreground"
                    }`}
                  >
                    {col.visible ? (
                      <Eye className="w-3.5 h-3.5" />
                    ) : (
                      <EyeOff className="w-3.5 h-3.5" />
                    )}
                  </button>
                </div>

                {/* Name / Info */}
                <div className="pr-2 flex flex-col justify-center overflow-hidden">
                  <div className="flex items-center gap-2">
                    <div
                      className="w-2 h-2 rounded-full shrink-0"
                      style={{
                        backgroundColor:
                          col.display_color || "var(--muted-foreground)",
                      }}
                      title={`Color: ${col.display_color || "Default"}`}
                    />
                    <span className="text-xs font-medium text-foreground truncate">
                      {col.name}
                    </span>
                    <ChevronRight className="w-3 h-3 text-muted-foreground/20 group-hover:text-muted-foreground/50 transition-colors" />
                  </div>
                  <span className="text-xs text-muted-foreground truncate font-mono">
                    {col.type === "value"
                      ? col.value_formula || "no formula"
                      : `${col.conditions?.length ?? 0} conditions`}
                  </span>
                </div>

                {/* Screener Filter State */}
                <div
                  className="flex justify-center"
                  onClick={(e) => e.stopPropagation()}
                >
                  <button
                    onClick={() =>
                      updateColumn(i, {
                        filter: FILTER_CYCLE[col.filter ?? "off"],
                      })
                    }
                    className={`p-1 rounded-sm transition-all border ${
                      col.filter === "active"
                        ? "text-green-500 bg-green-500/10 border-green-500/20"
                        : col.filter === "inactive"
                          ? "text-red-500 bg-red-500/10 border-red-500/20"
                          : "text-muted-foreground/40 border-transparent hover:border-border"
                    }`}
                    title={`Screener state: ${col.filter || "off"}`}
                  >
                    <Filter className="w-3.5 h-3.5" />
                  </button>
                </div>

                {/* Type Badge */}
                <div className="flex justify-center">
                  <span
                    className={`text-xs uppercase font-bold px-1.5 py-0.5 rounded-full ${
                      col.type === "value"
                        ? "text-blue-500 bg-blue-500/10 border border-blue-500/20"
                        : "text-amber-500 bg-amber-500/10 border border-amber-500/20"
                    }`}
                  >
                    {col.type === "value" ? "VAL" : "CND"}
                  </span>
                </div>

                {/* Delete */}
                <div
                  className="flex justify-center"
                  onClick={(e) => e.stopPropagation()}
                >
                  <button
                    onClick={() => removeColumn(i)}
                    className="p-1 rounded-sm text-muted-foreground/0 group-hover:text-muted-foreground/50 hover:text-red-500 hover:bg-red-500/10 transition-all opacity-0 group-hover:opacity-100"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            ))}

            {columns.length === 0 && (
              <div className="flex flex-col items-center justify-center py-12 text-muted-foreground bg-muted/5">
                <Plus className="w-8 h-8 opacity-10 mb-2" />
                <p className="text-xs">No columns defined for this set</p>
              </div>
            )}
          </div>

          {/* ─── Footer ────────────────────────────────────────── */}
          <div className="flex items-center gap-2 px-4 py-3 border-t border-border bg-muted/20 shrink-0">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="outline"
                  size="sm"
                  className="h-8 text-xs gap-1.5"
                >
                  <Plus className="w-3 h-3" />
                  Add Column
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="start" className="w-44">
                <DropdownMenuItem onClick={() => addColumn("value")}>
                  <div className="flex flex-col gap-0.5">
                    <span className="text-xs font-medium">Value Column</span>
                    <span className="text-xs text-muted-foreground">
                      Show calculated values
                    </span>
                  </div>
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => addColumn("condition")}>
                  <div className="flex flex-col gap-0.5">
                    <span className="text-xs font-medium">
                      Condition Column
                    </span>
                    <span className="text-xs text-muted-foreground">
                      True/False indicator
                    </span>
                  </div>
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>

            <div className="flex-1" />

            {hasChanges ? (
              <div className="flex items-center gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={onClose}
                  className="h-8 text-xs"
                >
                  Discard
                </Button>
                <Button
                  size="sm"
                  onClick={save}
                  disabled={updateColumnSet.isPending}
                  className="h-8 text-xs font-semibold"
                >
                  {updateColumnSet.isPending ? "Saving..." : "Save Changes"}
                </Button>
              </div>
            ) : (
              <Button
                variant="outline"
                size="sm"
                onClick={onClose}
                className="h-8 text-xs"
              >
                Done
              </Button>
            )}
          </div>
        </DialogContent>
      </Dialog>

      {/* ─── Column Properties Dialog (Secondary) ────────── */}
      <ColumnPropertiesDialog
        open={editingColIdx !== null}
        onClose={() => setEditingColIdx(null)}
        column={editingColIdx !== null ? columns[editingColIdx] : null}
        onSave={(updated) => {
          if (editingColIdx !== null) {
            updateColumn(editingColIdx, updated);
            setEditingColIdx(null);
          }
        }}
      />
    </>
  );
}
