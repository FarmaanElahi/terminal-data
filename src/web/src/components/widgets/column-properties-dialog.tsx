import { useState, useEffect } from "react";
import type {
  ColumnDef,
  ConditionDef,
  Timeframe,
  FilterEvaluateOn,
  TimeframeMode,
  EvaluateAs,
} from "@/types/models";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { FormulaEditor } from "./formula-editor";
import { X, Plus, Settings2 } from "lucide-react";

interface Props {
  open: boolean;
  onClose: () => void;
  column: ColumnDef | null;
  onSave: (column: ColumnDef) => void;
}

const TIMEFRAMES: { value: Timeframe; label: string }[] = [
  { value: "D", label: "D" },
  { value: "W", label: "W" },
  { value: "M", label: "M" },
  { value: "Y", label: "Y" },
];

const EVALUATE_ON: { value: FilterEvaluateOn; label: string }[] = [
  { value: "now", label: "Now" },
  { value: "x_bar_ago", label: "X Bar Ago" },
  { value: "within_x_bars", label: "Within X Bars" },
  { value: "x_bar_in_row", label: "X Bar in Row" },
];

const TIMEFRAME_MODES: { value: TimeframeMode; label: string }[] = [
  { value: "context", label: "Context (Inherit)" },
  { value: "fixed", label: "Fixed Timeframe" },
];

// ─── Internal Components ─────────────────────────────────────────────

function SettingsSection({
  title,
  children,
  className,
}: {
  title: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={`space-y-3 ${className}`}>
      <div className="flex items-center gap-2">
        <h4 className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground/70">
          {title}
        </h4>
        <div className="h-px flex-1 bg-border/50" />
      </div>
      <div className="space-y-4 px-0.5">{children}</div>
    </div>
  );
}

export function ColumnPropertiesDialog({
  open,
  onClose,
  column,
  onSave,
}: Props) {
  const [edited, setEdited] = useState<ColumnDef | null>(null);

  useEffect(() => {
    if (column) {
      setEdited({ ...column });
    } else {
      setEdited(null);
    }
  }, [column, open]);

  if (!edited) return null;

  const update = (patch: Partial<ColumnDef>) => {
    setEdited((prev) => (prev ? { ...prev, ...patch } : null));
  };

  const isValue = edited.type === "value";

  return (
    <Dialog open={open} onOpenChange={(io) => !io && onClose()}>
      <DialogContent className="sm:max-w-[600px] p-0 overflow-hidden gap-0">
        <DialogHeader className="px-6 py-4 border-b">
          <DialogTitle className="flex items-center gap-2">
            <Settings2 className="w-4 h-4 text-muted-foreground" />
            {edited.name || "New Column"}
          </DialogTitle>
        </DialogHeader>

        <Tabs defaultValue="formula" className="w-full">
          <div className="px-6 border-b bg-muted/20">
            <TabsList className="h-10 bg-transparent gap-4 p-0">
              <TabsTrigger
                value="formula"
                className="data-[state=active]:bg-transparent data-[state=active]:shadow-none data-[state=active]:border-b-2 data-[state=active]:border-primary rounded-none px-2 h-10 text-xs"
              >
                {isValue ? "Formula" : "Conditions"}
              </TabsTrigger>
              <TabsTrigger
                value="filter"
                className="data-[state=active]:bg-transparent data-[state=active]:shadow-none data-[state=active]:border-b-2 data-[state=active]:border-primary rounded-none px-2 h-10 text-xs"
              >
                Filter
              </TabsTrigger>
              <TabsTrigger
                value="display"
                className="data-[state=active]:bg-transparent data-[state=active]:shadow-none data-[state=active]:border-b-2 data-[state=active]:border-primary rounded-none px-2 h-10 text-xs"
              >
                Display
              </TabsTrigger>
            </TabsList>
          </div>

          <div className="p-0 h-[450px] overflow-hidden flex flex-col">
            <div className="flex-1 overflow-y-auto p-6 scrollbar-thin">
              {/* ─── Formula/Conditions Tab ────────────────────────── */}
              <TabsContent value="formula" className="mt-0 space-y-8 pb-4">
                {isValue ? (
                  <>
                    <SettingsSection title="Calculation Source">
                      <div className="space-y-2">
                        <Label className="text-[11px] text-muted-foreground">
                          Formula
                        </Label>
                        <FormulaEditor
                          value={edited.value_formula ?? ""}
                          onChange={(v) => update({ value_formula: v })}
                          height={160}
                        />
                      </div>
                    </SettingsSection>

                    <SettingsSection title="Evaluation Context">
                      <div className="grid grid-cols-2 gap-6">
                        <div className="space-y-2">
                          <Label className="text-[11px] text-muted-foreground">
                            Timeframe
                          </Label>
                          <Select
                            value={edited.value_formula_tf ?? "D"}
                            onValueChange={(v) =>
                              update({ value_formula_tf: v as Timeframe })
                            }
                          >
                            <SelectTrigger className="h-8 text-xs">
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
                        <div className="space-y-2">
                          <Label className="text-[11px] text-muted-foreground">
                            Bar Ago
                          </Label>
                          <Input
                            type="number"
                            min={0}
                            className="h-8 text-xs"
                            value={edited.value_formula_x_bar_ago ?? 0}
                            onChange={(e) =>
                              update({
                                value_formula_x_bar_ago:
                                  parseInt(e.target.value) || 0,
                              })
                            }
                          />
                        </div>
                      </div>
                      <div className="grid grid-cols-2 gap-6">
                        <div className="space-y-2">
                          <Label className="text-[11px] text-muted-foreground">
                            Refresh Interval (seconds)
                          </Label>
                          <Input
                            type="number"
                            min={0}
                            className="h-8 text-xs"
                            value={edited.value_formula_refresh_interval ?? 0}
                            onChange={(e) =>
                              update({
                                value_formula_refresh_interval:
                                  parseInt(e.target.value) || 0,
                              })
                            }
                          />
                        </div>
                      </div>
                    </SettingsSection>
                  </>
                ) : (
                  <ConditionsEditor
                    conditions={edited.conditions ?? []}
                    tf={edited.conditions_tf ?? "D"}
                    tfMode={edited.condition_tf_mode ?? "fixed"}
                    barAgo={edited.condition_value_x_bar_ago ?? 0}
                    logic={edited.conditions_logic ?? "and"}
                    onChange={(patch) => update(patch)}
                  />
                )}
              </TabsContent>

              {/* ─── Filter Tab ───────────────────────────────────── */}
              <TabsContent value="filter" className="mt-0 space-y-8">
                <SettingsSection title="Screener Filter">
                  <div className="space-y-4">
                    <div className="space-y-2">
                      <Label className="text-[11px] text-muted-foreground">
                        Status
                      </Label>
                      <Select
                        value={edited.filter ?? "off"}
                        onValueChange={(v) => {
                          const nextFilter = v as ColumnDef["filter"];
                          update({
                            filter: nextFilter,
                            ...(isValue
                              ? {
                                  value_formula_filter_enabled:
                                    nextFilter !== "off",
                                }
                              : {}),
                          });
                        }}
                      >
                        <SelectTrigger className="w-full h-8 text-xs">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="off">
                            Off (Visible Only)
                          </SelectItem>
                          <SelectItem value="active">
                            Active (Matches)
                          </SelectItem>
                          <SelectItem value="inactive">
                            Inactive (Does not match)
                          </SelectItem>
                        </SelectContent>
                      </Select>
                    </div>

                    {isValue && edited.filter !== "off" && (
                      <div className="space-y-6 pt-4 border-t animate-in fade-in slide-in-from-top-2 duration-200">
                        <div className="grid grid-cols-2 gap-6">
                          <div className="space-y-2">
                            <Label className="text-[11px] text-muted-foreground">
                              Operator
                            </Label>
                            <Select
                              value={edited.value_formula_filter_op ?? "gt"}
                              onValueChange={(v) =>
                                update({
                                  value_formula_filter_op: v as "gt" | "lt",
                                })
                              }
                            >
                              <SelectTrigger className="h-8 text-xs">
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent>
                                <SelectItem value="gt">
                                  Greater Than (&gt;)
                                </SelectItem>
                                <SelectItem value="lt">
                                  Less Than (&lt;)
                                </SelectItem>
                              </SelectContent>
                            </Select>
                          </div>
                          <div className="space-y-2">
                            <Label className="text-[11px] text-muted-foreground">
                              Threshold Value
                            </Label>
                            <Input
                              type="number"
                              className="h-8 text-xs"
                              value={String(
                                edited.value_formula_filter_params?.[0] ?? 0,
                              )}
                              onChange={(e) =>
                                update({
                                  value_formula_filter_params: [
                                    parseFloat(e.target.value) || 0,
                                  ],
                                })
                              }
                            />
                          </div>
                        </div>

                        <div className="grid grid-cols-2 gap-6">
                          <div className="space-y-2">
                            <Label className="text-[11px] text-muted-foreground">
                              Evaluation Mode
                            </Label>
                            <Select
                              value={
                                edited.value_formula_filter_evaluate_on ?? "now"
                              }
                              onValueChange={(v) =>
                                update({
                                  value_formula_filter_evaluate_on:
                                    v as FilterEvaluateOn,
                                })
                              }
                            >
                              <SelectTrigger className="h-8 text-xs">
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent>
                                {EVALUATE_ON.map((o) => (
                                  <SelectItem key={o.value} value={o.value}>
                                    {o.label}
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          </div>
                          {edited.value_formula_filter_evaluate_on !==
                            "now" && (
                            <div className="space-y-2">
                              <Label className="text-[11px] text-muted-foreground">
                                Bars Lookback
                              </Label>
                              <Input
                                type="number"
                                className="h-8 text-xs"
                                min={1}
                                value={String(
                                  edited
                                    .value_formula_filter_evaluate_on_params?.[0] ??
                                    1,
                                )}
                                onChange={(e) =>
                                  update({
                                    value_formula_filter_evaluate_on_params: [
                                      parseInt(e.target.value) || 1,
                                    ],
                                  })
                                }
                              />
                            </div>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                </SettingsSection>
              </TabsContent>

              {/* ─── Display Tab ──────────────────────────────────── */}
              <TabsContent
                value="display"
                className="mt-0 space-y-8 pb-4 focus-visible:outline-none"
              >
                <SettingsSection title="Identity">
                  <div className="space-y-2">
                    <Label className="text-[11px] text-muted-foreground">
                      Column Display Name
                    </Label>
                    <Input
                      className="h-8 text-xs"
                      value={edited.name}
                      onChange={(e) => update({ name: e.target.value })}
                    />
                  </div>
                </SettingsSection>

                <SettingsSection title="Visual Style">
                  <div className="grid grid-cols-2 gap-6">
                    <div className="space-y-2">
                      <Label className="text-[11px] text-muted-foreground">
                        Default Color
                      </Label>
                      <div className="flex items-center gap-2">
                        <Input
                          type="color"
                          className="h-8 w-10 p-1 shrink-0 bg-transparent"
                          value={edited.display_color || "#ffffff"}
                          onChange={(e) =>
                            update({ display_color: e.target.value })
                          }
                        />
                        <Input
                          className="h-8 text-[11px] font-mono flex-1"
                          value={edited.display_color || ""}
                          onChange={(e) =>
                            update({ display_color: e.target.value })
                          }
                          placeholder="#RRGGBB"
                        />
                      </div>
                    </div>
                    <div className="flex flex-col justify-end pb-1">
                      <div className="flex items-center gap-2">
                        <input
                          type="checkbox"
                          id="vis-toggle"
                          checked={edited.visible}
                          onChange={(e) =>
                            update({ visible: e.target.checked })
                          }
                          className="w-3.5 h-3.5 rounded-sm bg-muted border-border text-primary focus:ring-1 focus:ring-primary/20"
                        />
                        <Label
                          htmlFor="vis-toggle"
                          className="text-xs cursor-pointer select-none"
                        >
                          Visible in Table
                        </Label>
                      </div>
                    </div>
                  </div>
                </SettingsSection>

                <SettingsSection title="Numeric Highlighting">
                  <div className="grid grid-cols-2 gap-6">
                    <div className="space-y-2">
                      <Label className="text-[11px] text-muted-foreground">
                        Positive Value Color
                      </Label>
                      <div className="flex items-center gap-2">
                        <Input
                          type="color"
                          className="h-8 w-8 p-1 shrink-0 bg-transparent border-none"
                          value={
                            edited.display_numeric_positive_color ?? "#10b981"
                          }
                          onChange={(e) =>
                            update({
                              display_numeric_positive_color: e.target.value,
                            })
                          }
                        />
                        <Input
                          className="h-8 text-[11px] font-mono flex-1"
                          value={
                            edited.display_numeric_positive_color ?? "#10b981"
                          }
                          onChange={(e) =>
                            update({
                              display_numeric_positive_color: e.target.value,
                            })
                          }
                        />
                      </div>
                    </div>
                    <div className="space-y-2">
                      <Label className="text-[11px] text-muted-foreground">
                        Negative Value Color
                      </Label>
                      <div className="flex items-center gap-2">
                        <Input
                          type="color"
                          className="h-8 w-8 p-1 shrink-0 bg-transparent border-none"
                          value={
                            edited.display_numeric_negative_color ?? "#ef4444"
                          }
                          onChange={(e) =>
                            update({
                              display_numeric_negative_color: e.target.value,
                            })
                          }
                        />
                        <Input
                          className="h-8 text-[11px] font-mono flex-1"
                          value={
                            edited.display_numeric_negative_color ?? "#ef4444"
                          }
                          onChange={(e) =>
                            update({
                              display_numeric_negative_color: e.target.value,
                            })
                          }
                        />
                      </div>
                    </div>
                  </div>
                </SettingsSection>

                <SettingsSection title="Data Formatting">
                  <div className="grid grid-cols-2 gap-6">
                    <div className="space-y-2">
                      <Label className="text-[11px] text-muted-foreground">
                        Prefix
                      </Label>
                      <Input
                        className="h-8 text-xs font-mono"
                        value={edited.display_numeric_prefix ?? ""}
                        onChange={(e) =>
                          update({ display_numeric_prefix: e.target.value })
                        }
                        placeholder="$"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label className="text-[11px] text-muted-foreground">
                        Suffix
                      </Label>
                      <Input
                        className="h-8 text-xs font-mono"
                        value={edited.display_numeric_suffix ?? ""}
                        onChange={(e) =>
                          update({ display_numeric_suffix: e.target.value })
                        }
                        placeholder="%"
                      />
                    </div>
                  </div>
                  <div className="flex items-center gap-2 pt-2">
                    <input
                      type="checkbox"
                      id="show-pos-sign"
                      checked={
                        edited.display_numeric_show_positive_sign ?? false
                      }
                      onChange={(e) =>
                        update({
                          display_numeric_show_positive_sign: e.target.checked,
                        })
                      }
                      className="w-3.5 h-3.5 rounded-sm bg-muted border-border text-primary focus:ring-1 focus:ring-primary/20"
                    />
                    <Label
                      htmlFor="show-pos-sign"
                      className="text-xs cursor-pointer select-none"
                    >
                      Show positive (+) sign for upticks
                    </Label>
                  </div>
                  <div className="space-y-2 pt-2">
                    <Label className="text-[11px] text-muted-foreground">
                      Decimal Places
                    </Label>
                    <Input
                      type="number"
                      min={0}
                      max={8}
                      className="h-8 text-xs w-24"
                      value={edited.display_numeric_max_decimal ?? ""}
                      placeholder="Auto"
                      onChange={(e) =>
                        update({
                          display_numeric_max_decimal:
                            e.target.value === ""
                              ? null
                              : Number(e.target.value),
                        })
                      }
                    />
                  </div>
                </SettingsSection>
              </TabsContent>
            </div>
          </div>
        </Tabs>

        <DialogFooter className="px-6 py-4 border-t bg-muted/30">
          <Button variant="ghost" size="sm" onClick={onClose}>
            Cancel
          </Button>
          <Button size="sm" onClick={() => onSave(edited)}>
            Save Column
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function ConditionsEditor({
  conditions,
  tf,
  tfMode,
  barAgo,
  logic,
  onChange,
}: {
  conditions: ConditionDef[];
  tf: Timeframe;
  tfMode: TimeframeMode;
  barAgo: number;
  logic: "and" | "or";
  onChange: (patch: Partial<ColumnDef>) => void;
}) {
  const updateCond = (idx: number, patch: Partial<ConditionDef>) => {
    const next = [...conditions];
    next[idx] = { ...next[idx], ...patch };
    onChange({ conditions: next });
  };

  const addCond = () => {
    onChange({
      conditions: [...conditions, { formula: "", evaluate_as: "true" }],
    });
  };

  const removeCond = (idx: number) => {
    onChange({ conditions: conditions.filter((_, i) => i !== idx) });
  };

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label className="text-xs font-semibold">Logic</Label>
          <Select
            value={logic}
            onValueChange={(v) =>
              onChange({ conditions_logic: v as "and" | "or" })
            }
          >
            <SelectTrigger className="h-9">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="and">All (AND)</SelectItem>
              <SelectItem value="or">Any (OR)</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-2">
          <Label className="text-xs font-semibold">Timeframe Mode</Label>
          <Select
            value={tfMode}
            onValueChange={(v) =>
              onChange({ condition_tf_mode: v as TimeframeMode })
            }
          >
            <SelectTrigger className="h-9">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {TIMEFRAME_MODES.map((tm) => (
                <SelectItem key={tm.value} value={tm.value}>
                  {tm.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label className="text-xs font-semibold">Timeframe</Label>
          <Select
            disabled={tfMode === "context"}
            value={tf}
            onValueChange={(v) => onChange({ conditions_tf: v as Timeframe })}
          >
            <SelectTrigger className="h-9">
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
        <div className="space-y-2">
          <Label className="text-xs font-semibold">Bar Ago</Label>
          <Input
            type="number"
            min={0}
            value={barAgo}
            onChange={(e) =>
              onChange({
                condition_value_x_bar_ago: parseInt(e.target.value) || 0,
              })
            }
            className="h-9"
          />
        </div>
      </div>

      <div className="space-y-2 pt-2">
        <Label className="text-xs font-semibold flex justify-between items-center">
          Evaluate Conditions
          <Button
            variant="ghost"
            size="sm"
            className="h-6 text-xs px-2"
            onClick={addCond}
          >
            <Plus className="w-3 h-3 mr-1" /> Add
          </Button>
        </Label>
        <div className="space-y-3">
          {conditions.map((c, i) => (
            <div
              key={i}
              className="flex flex-col gap-2 p-3 border rounded-md bg-muted/10 relative group"
            >
              <Button
                variant="ghost"
                size="icon"
                className="h-6 w-6 absolute -top-1 -right-1 opacity-0 group-hover:opacity-100 transition-opacity text-muted-foreground hover:text-red-500"
                onClick={() => removeCond(i)}
              >
                <X className="w-3 h-3" />
              </Button>

              <div className="space-y-1.5">
                <FormulaEditor
                  value={c.formula}
                  onChange={(v) => updateCond(i, { formula: v })}
                  height={64}
                />
              </div>

              <div className="flex items-center gap-2">
                <Select
                  value={c.evaluate_as ?? "true"}
                  onValueChange={(v) => {
                    const nextEval = v as EvaluateAs;
                    let nextParams: any[] = [];
                    if (nextEval === "gt" || nextEval === "lt")
                      nextParams = [0];
                    if (nextEval === "in_between") nextParams = [0, 100];
                    if (nextEval === "rank") nextParams = [10];

                    updateCond(i, {
                      evaluate_as: nextEval,
                      evaluate_as_params: nextParams,
                    });
                  }}
                >
                  <SelectTrigger className="h-8 w-32 text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="true">Is True</SelectItem>
                    <SelectItem value="gt">Greater Than</SelectItem>
                    <SelectItem value="lt">Less Than</SelectItem>
                    <SelectItem value="in_between">In Between</SelectItem>
                    <SelectItem value="rank">Rank (Top X)</SelectItem>
                  </SelectContent>
                </Select>

                {(c.evaluate_as === "gt" ||
                  c.evaluate_as === "lt" ||
                  c.evaluate_as === "rank") && (
                  <Input
                    type="number"
                    className="h-8 w-20 text-xs"
                    value={String(c.evaluate_as_params?.[0] ?? 0)}
                    onChange={(e) =>
                      updateCond(i, {
                        evaluate_as_params: [parseFloat(e.target.value) || 0],
                      })
                    }
                  />
                )}
                {c.evaluate_as === "in_between" && (
                  <div className="flex items-center gap-1">
                    <Input
                      type="number"
                      className="h-8 w-16 text-xs"
                      value={String(c.evaluate_as_params?.[0] ?? 0)}
                      onChange={(e) =>
                        updateCond(i, {
                          evaluate_as_params: [
                            parseFloat(e.target.value) || 0,
                            c.evaluate_as_params?.[1] ?? 100,
                          ],
                        })
                      }
                    />
                    <span className="text-[10px] text-muted-foreground">
                      to
                    </span>
                    <Input
                      type="number"
                      className="h-8 w-16 text-xs"
                      value={String(c.evaluate_as_params?.[1] ?? 100)}
                      onChange={(e) =>
                        updateCond(i, {
                          evaluate_as_params: [
                            c.evaluate_as_params?.[0] ?? 0,
                            parseFloat(e.target.value) || 0,
                          ],
                        })
                      }
                    />
                  </div>
                )}
              </div>
            </div>
          ))}
          {conditions.length === 0 && (
            <div className="text-center py-4 text-xs text-muted-foreground border border-dashed rounded-md">
              No conditions added
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
