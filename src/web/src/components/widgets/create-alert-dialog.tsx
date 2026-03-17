import { useState, useEffect, useMemo, useRef } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Bell, Plus, Zap, TrendingUp, Minus, Music, Play } from "lucide-react";
import { cn } from "@/lib/utils";
import { playBeep } from "@/lib/audio";
import { useCreateAlert, useUpdateAlert } from "@/queries/use-alerts";
import type {
  Alert,
  AlertCreateParams,
  AlertUpdateParams,
  AlertType,
  AlertFrequency,
  GuardCondition,
} from "@/types/alert";
import { toast } from "sonner";

// ── Props ───────────────────────────────────────────────────────────

interface CreateAlertDialogProps {
  open: boolean;
  onClose: () => void;
  /** Pre-fill symbol from chart context */
  defaultSymbol?: string;
  /** Pre-fill drawing data for drawing-based alerts */
  drawingData?: {
    drawingId: string;
    drawingType: "trendline" | "hline" | "rectangle";
    /** For trendline: two anchor points */
    points?: { time: number; price: number }[];
    /** For hline */
    price?: number;
    /** For rectangle */
    top?: number;
    bottom?: number;
    left?: number;
    right?: number;
  };
  /** If provided, dialog is in "edit" mode */
  editAlert?: Alert;
  onCreated?: (alert: Alert) => void;
}

// ── Constants ───────────────────────────────────────────────────────

const ALERT_TYPE_OPTIONS: {
  value: AlertType;
  label: string;
  icon: typeof Zap;
  description: string;
}[] = [
  {
    value: "formula",
    label: "Formula",
    icon: Zap,
    description: "Condition using formula expressions",
  },
  {
    value: "drawing",
    label: "Drawing",
    icon: TrendingUp,
    description: "Based on chart drawing price levels",
  },
];

const FREQUENCY_OPTIONS: { value: AlertFrequency; label: string }[] = [
  { value: "once", label: "Fire once" },
  { value: "once_per_minute", label: "Once per minute" },
  { value: "once_per_bar", label: "Once per bar" },
  { value: "end_of_day", label: "End of day" },
];

const DRAWING_TRIGGER_OPTIONS: Record<
  string,
  { value: string; label: string }[]
> = {
  trendline: [
    { value: "crosses_above", label: "Price crosses above" },
    { value: "crosses_below", label: "Price crosses below" },
  ],
  hline: [
    { value: "crosses_above", label: "Price crosses above" },
    { value: "crosses_below", label: "Price crosses below" },
  ],
  rectangle: [
    { value: "enters", label: "Price enters zone" },
    { value: "exits", label: "Price exits zone" },
    { value: "enters_or_exits", label: "Price enters or exits" },
  ],
};

const SOUND_OPTIONS = [
  { value: "none", label: "None" },
  { value: "beep", label: "Standard Beep" },
  { value: "buzzer", label: "Buzzer" },
  { value: "digital", label: "Digital" },
  { value: "chime", label: "Chime" },
];

// ── Component ───────────────────────────────────────────────────────

export function CreateAlertDialog({
  open,
  onClose,
  defaultSymbol = "",
  drawingData,
  editAlert,
  onCreated,
}: CreateAlertDialogProps) {
  const createAlert = useCreateAlert();
  const updateAlert = useUpdateAlert();
  const isEditing = !!editAlert;

  // ── State ───────────────────────────────────────────────────────
  const [name, setName] = useState("");
  const [symbol, setSymbol] = useState("");
  const [alertType, setAlertType] = useState<AlertType>("formula");
  const [frequency, setFrequency] = useState<AlertFrequency>("once");

  // Formula
  const [formula, setFormula] = useState("");
  const [guardFormulas, setGuardFormulas] = useState<string[]>([]);

  // Drawing
  const [drawingTrigger, setDrawingTrigger] = useState("crosses_above");
  const [alertSound, setAlertSound] = useState<string>("beep");
  const initialMount = useRef(true);

  // Sound preview when selection changes
  useEffect(() => {
    if (initialMount.current) {
      initialMount.current = false;
      return;
    }
    if (alertSound !== "none") {
      playBeep(alertSound);
    }
  }, [alertSound]);

  // ── Initialize state ──────────────────────────────────────────
  useEffect(() => {
    if (!open) return;

    // Suppress the sound preview triggered by programmatic state resets below
    initialMount.current = true;

    if (editAlert) {
      setName(editAlert.name);
      setSymbol(editAlert.symbol);
      setAlertType(editAlert.alert_type as AlertType);
      setFrequency(editAlert.frequency as AlertFrequency);
      setAlertSound(editAlert.alert_sound || "none");

      const cond = editAlert.trigger_condition;
      if (editAlert.alert_type === "formula") {
        setFormula((cond as { formula?: string }).formula || "");
      } else {
        setDrawingTrigger(
          (cond as { trigger_when?: string }).trigger_when || "crosses_above",
        );
      }

      const guards = editAlert.guard_conditions || [];
      setGuardFormulas(
        guards.map((g: GuardCondition) => g.formula || ""),
      );
    } else {
      // Create mode
      setName("");
      setSymbol(defaultSymbol);
      setFrequency("once");
      setFormula("");
      setGuardFormulas([]);
      setDrawingTrigger("crosses_above");
      setAlertSound("beep");

      if (drawingData) {
        setAlertType("drawing");
      } else {
        setAlertType("formula");
      }
    }
  }, [open, editAlert, defaultSymbol, drawingData]);

  // ── Build trigger condition ───────────────────────────────────
  const buildTriggerCondition = (): Record<string, unknown> => {
    if (alertType === "formula") {
      return { formula };
    }

    // Drawing-based
    if (!drawingData) return {};

    const base: Record<string, unknown> = {
      drawing_type: drawingData.drawingType,
      trigger_when: drawingTrigger,
    };

    if (drawingData.drawingType === "trendline" && drawingData.points) {
      base.points = drawingData.points;
    } else if (drawingData.drawingType === "hline") {
      base.price = drawingData.price;
    } else if (drawingData.drawingType === "rectangle") {
      base.top = drawingData.top;
      base.bottom = drawingData.bottom;
      base.left = drawingData.left;
      base.right = drawingData.right;
    }

    return base;
  };

  // ── Validation ────────────────────────────────────────────────
  const canSubmit = useMemo(() => {
    if (!symbol.trim()) return false;
    if (alertType === "formula" && !formula.trim()) return false;
    if (alertType === "drawing" && !drawingData) return false;
    return true;
  }, [symbol, alertType, formula, drawingData]);

  // ── Submit ────────────────────────────────────────────────────
  const handleSubmit = async () => {
    if (!canSubmit) return;

    const triggerCondition = buildTriggerCondition();
    const guards = guardFormulas
      .filter((f) => f.trim())
      .map((f) => ({ formula: f.trim() }));

    if (isEditing && editAlert) {
      const data: AlertUpdateParams = {
        name: name.trim() || undefined,
        trigger_condition: triggerCondition,
        guard_conditions: guards.length > 0 ? guards : undefined,
        frequency,
        alert_sound: alertSound,
      };

      try {
        const updated = await updateAlert.mutateAsync({
          id: editAlert.id,
          data,
        });
        toast.success("Alert updated");
        onCreated?.(updated);
        onClose();
      } catch {
        toast.error("Failed to update alert");
      }
    } else {
      const data: AlertCreateParams = {
        name: name.trim(),
        symbol: symbol.trim(),
        alert_type: alertType,
        trigger_condition: triggerCondition,
        guard_conditions: guards,
        frequency,
        alert_sound: alertSound,
        drawing_id: drawingData?.drawingId,
      };

      try {
        const created = await createAlert.mutateAsync(data);
        toast.success("Alert created");
        onCreated?.(created);
        onClose();
      } catch {
        toast.error("Failed to create alert");
      }
    }
  };

  // ── Render ────────────────────────────────────────────────────
  const drawingType = drawingData?.drawingType || "trendline";
  const triggerOptions = DRAWING_TRIGGER_OPTIONS[drawingType] || [];
  const isPending = createAlert.isPending || updateAlert.isPending;

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="sm:max-w-lg p-0 overflow-hidden gap-0">
        <DialogHeader className="px-6 py-4 border-b">
          <DialogTitle className="text-base flex items-center gap-2">
            <Bell className="w-4 h-4 text-primary" />
            {isEditing ? "Edit Alert" : "Create Alert"}
          </DialogTitle>
        </DialogHeader>

        <div className="p-6 space-y-5 max-h-[70vh] overflow-y-auto">
          {/* Name */}
          <div className="space-y-1.5">
            <Label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Name (optional)
            </Label>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. NIFTY breakout"
              className="h-9"
              autoComplete="off"
            />
          </div>

          {/* Symbol */}
          <div className="space-y-1.5">
            <Label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Symbol
            </Label>
            <Input
              value={symbol}
              onChange={(e) => setSymbol(e.target.value.toUpperCase())}
              placeholder="e.g. NSE:RELIANCE"
              className="h-9 font-mono"
              autoComplete="off"
              disabled={isEditing}
            />
          </div>

          {/* Alert Type — only show in create mode without drawing */}
          {!isEditing && !drawingData && (
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Alert Type
              </Label>
              <div className="grid grid-cols-2 gap-2">
                {ALERT_TYPE_OPTIONS.map((opt) => {
                  const Icon = opt.icon;
                  const selected = alertType === opt.value;
                  return (
                    <button
                      key={opt.value}
                      onClick={() => setAlertType(opt.value)}
                      className={cn(
                        "flex flex-col items-center gap-1.5 rounded-lg border p-3 text-center transition-all",
                        selected
                          ? "border-primary bg-primary/5 text-foreground"
                          : "border-border text-muted-foreground hover:border-primary/40 hover:bg-muted/30",
                      )}
                    >
                      <Icon className="w-4 h-4" />
                      <span className="text-xs font-medium">{opt.label}</span>
                      <span className="text-[10px] leading-tight opacity-70">
                        {opt.description}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {/* Drawing info badge */}
          {drawingData && (
            <div className="flex items-center gap-2">
              <Badge variant="secondary" className="text-[10px]">
                {drawingData.drawingType}
              </Badge>
              <span className="text-[10px] text-muted-foreground">
                Drawing-based alert
              </span>
            </div>
          )}

          {/* Formula condition */}
          {alertType === "formula" && (
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Trigger Condition
              </Label>
              <Textarea
                value={formula}
                onChange={(e) => setFormula(e.target.value)}
                placeholder="e.g. C > 1500 or RSI(C,14) > 80"
                className="font-mono text-xs min-h-[80px] resize-none"
                autoComplete="off"
              />
            </div>
          )}

          {/* Drawing trigger */}
          {alertType === "drawing" && drawingData && (
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Trigger When
              </Label>
              <Select value={drawingTrigger} onValueChange={setDrawingTrigger}>
                <SelectTrigger className="h-9 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {triggerOptions.map((opt) => (
                    <SelectItem key={opt.value} value={opt.value}>
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>

              {/* Drawing data summary */}
              <div className="rounded-md border border-border bg-muted/20 p-3 space-y-1">
                <span className="text-[10px] uppercase font-semibold text-muted-foreground">
                  Drawing Data
                </span>
                {drawingData.drawingType === "hline" && (
                  <p className="text-xs font-mono">
                    Price: {drawingData.price?.toFixed(2)}
                  </p>
                )}
                {drawingData.drawingType === "trendline" &&
                  drawingData.points && (
                    <div className="text-xs font-mono space-y-0.5">
                      {drawingData.points.map((pt, i) => (
                        <p key={i}>
                          Point {i + 1}: ₹{pt.price.toFixed(2)} @{" "}
                          {new Date(pt.time * 1000).toLocaleDateString()}
                        </p>
                      ))}
                    </div>
                  )}
                {drawingData.drawingType === "rectangle" && (
                  <div className="text-xs font-mono space-y-0.5">
                    <p>
                      Top: ₹{drawingData.top?.toFixed(2)} | Bottom: ₹
                      {drawingData.bottom?.toFixed(2)}
                    </p>
                    <p>
                      {new Date(
                        (drawingData.left || 0) * 1000,
                      ).toLocaleDateString()}{" "}
                      →{" "}
                      {new Date(
                        (drawingData.right || 0) * 1000,
                      ).toLocaleDateString()}
                    </p>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Guard conditions */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <Label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Guard Conditions (optional)
              </Label>
              <Button
                size="sm"
                variant="ghost"
                className="h-6 text-[10px] px-2"
                onClick={() => setGuardFormulas((prev) => [...prev, ""])}
              >
                <Plus className="w-3 h-3 mr-1" />
                Add
              </Button>
            </div>
            <p className="text-[10px] text-muted-foreground">
              Extra formula conditions that must all be true for the alert to
              fire.
            </p>
            {guardFormulas.map((g, i) => (
              <div key={i} className="flex items-center gap-1.5">
                <Input
                  value={g}
                  onChange={(e) => {
                    const next = [...guardFormulas];
                    next[i] = e.target.value;
                    setGuardFormulas(next);
                  }}
                  placeholder={`e.g. V > 100000`}
                  className="h-8 font-mono text-xs flex-1"
                  autoComplete="off"
                />
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-8 w-8 p-0 text-muted-foreground hover:text-destructive shrink-0"
                  onClick={() =>
                    setGuardFormulas((prev) => prev.filter((_, j) => j !== i))
                  }
                >
                  <Minus className="w-3 h-3" />
                </Button>
              </div>
            ))}
          </div>

          {/* Frequency */}
          <div className="space-y-1.5">
            <Label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Frequency
            </Label>
            <Select
              value={frequency}
              onValueChange={(v) => setFrequency(v as AlertFrequency)}
            >
              <SelectTrigger className="h-9 text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {FREQUENCY_OPTIONS.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Sound Setting */}
          <div className="space-y-1.5">
            <Label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center justify-between">
              Alert Sound
              <Button
                size="sm"
                variant="ghost"
                className="h-5 px-1.5 text-[9px] hover:text-primary"
                onClick={() => playBeep(alertSound)}
                disabled={alertSound === "none"}
              >
                <Play className="w-2.5 h-2.5 mr-1" />
                Listen
              </Button>
            </Label>
            <Select value={alertSound} onValueChange={setAlertSound}>
              <SelectTrigger className="h-9 text-xs">
                <Music className="w-3.5 h-3.5 mr-2 text-primary" />
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {SOUND_OPTIONS.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-[10px] text-muted-foreground mt-1 px-1">
              Select the audio feedback to play when this alert triggers in-app.
            </p>
          </div>
        </div>

        <DialogFooter className="px-6 py-4 bg-muted/30 border-t flex sm:justify-between items-center">
          <Button
            variant="ghost"
            size="sm"
            onClick={onClose}
            className="h-8 text-xs"
          >
            Cancel
          </Button>
          <Button
            size="sm"
            onClick={handleSubmit}
            disabled={!canSubmit || isPending}
            className="h-8 text-xs px-4"
          >
            {isPending
              ? isEditing
                ? "Saving..."
                : "Creating..."
              : isEditing
                ? "Save Changes"
                : "Create Alert"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
