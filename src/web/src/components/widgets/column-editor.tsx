import { useState, useCallback, useEffect } from "react";
import { columnsApi } from "@/lib/api";
import { useAuthStore } from "@/stores/auth-store";
import type {
  ColumnSet,
  ColumnDef,
  ConditionDef,
  FilterState,
} from "@/types/models";
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
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { FormulaEditor } from "./formula-editor";
import { Eye, EyeOff, X, Plus, Filter } from "lucide-react";

// ─── Helpers ─────────────────────────────────────────────────────────

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
  };
}

function newConditionColumn(): ColumnDef {
  return {
    id: makeId(),
    name: "New Condition",
    visible: true,
    type: "condition",
    filter: "off",
    conditions: [{ formula: "C > C.1", evaluate_as: "true" }],
    conditions_logic: "and",
    conditions_tf: "D",
  };
}

const FILTER_CYCLE: Record<FilterState, FilterState> = {
  off: "active",
  active: "inactive",
  inactive: "off",
};

// ─── Condition Row ───────────────────────────────────────────────────

function ConditionRow({
  cond,
  onChange,
  onRemove,
}: {
  cond: ConditionDef;
  onChange: (patch: Partial<ConditionDef>) => void;
  onRemove: () => void;
}) {
  return (
    <div className="flex items-center gap-1.5">
      <div className="flex-1">
        <FormulaEditor
          value={cond.formula}
          onChange={(v) => onChange({ formula: v })}
          height={26}
        />
      </div>
      <Select
        value={cond.evaluate_as ?? "true"}
        onValueChange={(v) =>
          onChange({ evaluate_as: v as ConditionDef["evaluate_as"] })
        }
      >
        <SelectTrigger className="h-6 w-20 text-[10px] shrink-0">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="true">Is True</SelectItem>
          <SelectItem value="gt">Greater</SelectItem>
          <SelectItem value="lt">Less</SelectItem>
          <SelectItem value="in_between">Between</SelectItem>
          <SelectItem value="rank">Rank</SelectItem>
        </SelectContent>
      </Select>
      <button
        onClick={onRemove}
        className="p-0.5 text-muted-foreground/40 hover:text-red-500 transition-colors shrink-0"
      >
        <X className="w-3 h-3" />
      </button>
    </div>
  );
}

// ─── Detail Panel ────────────────────────────────────────────────────

function ColumnDetail({
  col,
  onChange,
}: {
  col: ColumnDef;
  onChange: (patch: Partial<ColumnDef>) => void;
}) {
  if (col.type === "value") {
    return (
      <div className="p-3 space-y-3 border-t border-border bg-muted/10">
        {/* Formula */}
        <div className="space-y-1">
          <Label className="text-[10px] uppercase tracking-wider text-muted-foreground">
            Formula
          </Label>
          <FormulaEditor
            value={col.value_formula ?? ""}
            onChange={(v) => onChange({ value_formula: v })}
            height={28}
          />
        </div>

        {/* Timeframe + Bar Ago */}
        <div className="flex gap-2">
          <div className="space-y-1">
            <Label className="text-[10px] uppercase tracking-wider text-muted-foreground">
              Timeframe
            </Label>
            <Select
              value={col.value_formula_tf ?? "D"}
              onValueChange={(v) =>
                onChange({
                  value_formula_tf: v as ColumnDef["value_formula_tf"],
                })
              }
            >
              <SelectTrigger className="h-7 w-16 text-xs">
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
          <div className="space-y-1">
            <Label className="text-[10px] uppercase tracking-wider text-muted-foreground">
              Bar Ago
            </Label>
            <Input
              type="number"
              value={col.value_formula_x_bar_ago ?? 0}
              onChange={(e) =>
                onChange({
                  value_formula_x_bar_ago: parseInt(e.target.value) || 0,
                })
              }
              className="h-7 w-16 text-xs"
              min={0}
            />
          </div>
        </div>

        {/* Filter toggle */}
        <div className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={col.value_formula_filter_enabled ?? false}
            onChange={(e) =>
              onChange({ value_formula_filter_enabled: e.target.checked })
            }
            className="rounded-sm"
            id={`filter-${col.id}`}
          />
          <Label
            htmlFor={`filter-${col.id}`}
            className="text-[10px] uppercase tracking-wider text-muted-foreground cursor-pointer"
          >
            Enable Filter
          </Label>
          {col.value_formula_filter_enabled && (
            <Select
              value={col.value_formula_filter_op ?? "gt"}
              onValueChange={(v) =>
                onChange({
                  value_formula_filter_op:
                    v as ColumnDef["value_formula_filter_op"],
                })
              }
            >
              <SelectTrigger className="h-6 w-16 text-[10px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="gt">&gt;</SelectItem>
                <SelectItem value="lt">&lt;</SelectItem>
              </SelectContent>
            </Select>
          )}
        </div>
      </div>
    );
  }

  // ── Condition column detail ──
  const conditions = col.conditions ?? [];

  const updateCondition = (idx: number, patch: Partial<ConditionDef>) => {
    const next = [...conditions];
    next[idx] = { ...next[idx], ...patch };
    onChange({ conditions: next });
  };

  const addCondition = () => {
    onChange({
      conditions: [...conditions, { formula: "", evaluate_as: "true" }],
    });
  };

  const removeCondition = (idx: number) => {
    onChange({ conditions: conditions.filter((_, i) => i !== idx) });
  };

  return (
    <div className="p-3 space-y-3 border-t border-border bg-muted/10">
      {/* Timeframe + Logic */}
      <div className="flex gap-2 items-end">
        <div className="space-y-1">
          <Label className="text-[10px] uppercase tracking-wider text-muted-foreground">
            Timeframe
          </Label>
          <Select
            value={col.conditions_tf ?? "D"}
            onValueChange={(v) =>
              onChange({ conditions_tf: v as ColumnDef["conditions_tf"] })
            }
          >
            <SelectTrigger className="h-7 w-16 text-xs">
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
        <div className="space-y-1">
          <Label className="text-[10px] uppercase tracking-wider text-muted-foreground">
            Logic
          </Label>
          <Select
            value={col.conditions_logic ?? "and"}
            onValueChange={(v) =>
              onChange({
                conditions_logic: v as ColumnDef["conditions_logic"],
              })
            }
          >
            <SelectTrigger className="h-7 w-16 text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="and">AND</SelectItem>
              <SelectItem value="or">OR</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Conditions list */}
      <div className="space-y-1.5">
        <Label className="text-[10px] uppercase tracking-wider text-muted-foreground">
          Conditions
        </Label>
        {conditions.map((cond, idx) => (
          <ConditionRow
            key={idx}
            cond={cond}
            onChange={(patch) => updateCondition(idx, patch)}
            onRemove={() => removeCondition(idx)}
          />
        ))}
        <button
          onClick={addCondition}
          className="flex items-center gap-1 text-[10px] text-muted-foreground hover:text-foreground transition-colors py-1"
        >
          <Plus className="w-3 h-3" />
          Add Condition
        </button>
      </div>
    </div>
  );
}

// ─── Main Component ──────────────────────────────────────────────────

export function ColumnEditor({ open, onClose, columnSet }: ColumnEditorProps) {
  const [columns, setColumns] = useState<ColumnDef[]>([]);
  const [isSaving, setIsSaving] = useState(false);
  const [hasChanges, setHasChanges] = useState(false);
  const [expandedIdx, setExpandedIdx] = useState<number | null>(null);
  const [editingNameIdx, setEditingNameIdx] = useState<number | null>(null);

  useEffect(() => {
    if (open) {
      setColumns([...columnSet.columns]);
      setHasChanges(false);
      setExpandedIdx(null);
      setEditingNameIdx(null);
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
    setExpandedIdx(null);
    setHasChanges(true);
  }, []);

  const addColumn = useCallback(
    (type: "value" | "condition") => {
      const col = type === "value" ? newValueColumn() : newConditionColumn();
      setColumns((prev) => [...prev, col]);
      setExpandedIdx(columns.length);
      setHasChanges(true);
    },
    [columns.length],
  );

  const save = useCallback(async () => {
    setIsSaving(true);
    try {
      const { data } = await columnsApi.update(columnSet.id, {
        columns: columns as unknown as ColumnDef[],
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
        {/* ─── Header ────────────────────────────────────────── */}
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
        <div className="grid grid-cols-[36px_1fr_50px_50px_32px] items-center px-2 py-1.5 border-b border-border bg-muted/30 text-[10px] uppercase tracking-wider text-muted-foreground font-medium">
          <div className="text-center">Vis</div>
          <div>Column Name</div>
          <div className="text-center">Filter</div>
          <div className="text-center">Type</div>
          <div />
        </div>

        {/* ─── Column Rows ───────────────────────────────────── */}
        <div className="overflow-auto max-h-[60vh]">
          {columns.map((col, i) => (
            <div key={col.id}>
              {/* Summary row */}
              <div
                className={`grid grid-cols-[36px_1fr_50px_50px_32px] items-center px-2 border-b border-border/50 transition-colors cursor-pointer ${
                  expandedIdx === i ? "bg-muted/40" : "hover:bg-muted/20"
                }`}
                style={{ minHeight: "34px" }}
                onClick={() => setExpandedIdx(expandedIdx === i ? null : i)}
              >
                {/* Visible */}
                <div
                  className="flex justify-center"
                  onClick={(e) => e.stopPropagation()}
                >
                  <button
                    onClick={() => updateColumn(i, { visible: !col.visible })}
                    className={`p-1 rounded-sm transition-colors ${
                      col.visible
                        ? "text-foreground hover:text-muted-foreground"
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

                {/* Name */}
                <div
                  className="pr-1.5 py-1"
                  onClick={(e) => e.stopPropagation()}
                >
                  {editingNameIdx === i ? (
                    <Input
                      value={col.name}
                      onChange={(e) =>
                        updateColumn(i, { name: e.target.value })
                      }
                      onBlur={() => setEditingNameIdx(null)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") setEditingNameIdx(null);
                      }}
                      className="h-6 text-xs"
                      autoFocus
                    />
                  ) : (
                    <button
                      onClick={() => setEditingNameIdx(i)}
                      className="text-xs text-foreground truncate text-left w-full"
                    >
                      {col.name}
                      <span className="ml-2 text-muted-foreground text-[10px]">
                        {col.type === "value"
                          ? (col.value_formula ?? "")
                          : `${col.conditions?.length ?? 0} cond`}
                      </span>
                    </button>
                  )}
                </div>

                {/* Filter */}
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
                    className={`p-1 rounded-sm transition-colors ${
                      col.filter === "active"
                        ? "text-blue-400 bg-blue-500/15"
                        : col.filter === "inactive"
                          ? "text-red-400 bg-red-500/10"
                          : "text-muted-foreground/30 hover:text-muted-foreground"
                    }`}
                  >
                    <Filter className="w-3.5 h-3.5" />
                  </button>
                </div>

                {/* Type badge */}
                <div className="flex justify-center">
                  <span
                    className={`text-[9px] uppercase font-medium px-1.5 py-0.5 rounded ${
                      col.type === "value"
                        ? "text-blue-400 bg-blue-500/10"
                        : "text-amber-400 bg-amber-500/10"
                    }`}
                  >
                    {col.type === "value" ? "Val" : "Cnd"}
                  </span>
                </div>

                {/* Delete */}
                <div
                  className="flex justify-center"
                  onClick={(e) => e.stopPropagation()}
                >
                  <button
                    onClick={() => removeColumn(i)}
                    className="p-1 rounded-sm text-muted-foreground/30 hover:text-red-500 hover:bg-red-500/10 transition-colors"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>

              {/* Expanded detail panel */}
              {expandedIdx === i && (
                <ColumnDetail
                  col={col}
                  onChange={(patch) => updateColumn(i, patch)}
                />
              )}
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
            onClick={() => addColumn("value")}
            className="text-xs h-7"
          >
            <Plus className="w-3 h-3 mr-1" />
            Value Column
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => addColumn("condition")}
            className="text-xs h-7"
          >
            <Plus className="w-3 h-3 mr-1" />
            Condition Column
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
