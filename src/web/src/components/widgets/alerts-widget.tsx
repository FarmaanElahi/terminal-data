import { useState, useMemo } from "react";
import {
  Bell,
  BellOff,
  Trash2,
  Play,
  Pause,
  Clock,
  History,
  Zap,
  Plus,
  Edit2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { WidgetProps } from "@/types/layout";
import type { Alert } from "@/types/alert";
import {
  useAlerts,
  useAlertLogs,
  useDeleteAlert,
  useActivateAlert,
  usePauseAlert,
  useMarkLogsRead,
  useDeleteLog,
  useClearLogs,
} from "@/queries/use-alerts";
import { useWidget } from "@/hooks/use-widget";
import { toast } from "sonner";
import { CreateAlertDialog } from "./create-alert-dialog";

type Tab = "alerts" | "logs";

const STATUS_COLORS: Record<string, string> = {
  active: "text-emerald-400",
  paused: "text-muted-foreground",
  triggered: "text-amber-500",
  expired: "text-red-400",
};

const FREQ_LABELS: Record<string, string> = {
  once: "Once",
  once_per_minute: "1/min",
  once_per_bar: "1/bar",
  end_of_day: "EOD",
};

export function AlertsWidget({ instanceId }: WidgetProps) {
  const [tab, setTab] = useState<Tab>("alerts");
  const [showCreate, setShowCreate] = useState(false);
  const [editingAlert, setEditingAlert] = useState<Alert | undefined>(undefined);

  const handleEdit = (alert: Alert) => {
    setEditingAlert(alert);
    setShowCreate(true);
  };

  const handleClose = () => {
    setShowCreate(false);
    setEditingAlert(undefined);
  };

  return (
    <div className="h-full flex flex-col">
      {/* Tab bar */}
      <div className="flex border-b border-border shrink-0">
        <button
          className={`flex-1 px-3 py-1.5 text-xs font-medium transition-colors ${
            tab === "alerts"
              ? "text-foreground border-b-2 border-primary"
              : "text-muted-foreground hover:text-foreground"
          }`}
          onClick={() => setTab("alerts")}
        >
          <Bell className="w-3 h-3 inline mr-1" />
          Alerts
        </button>
        <button
          className={`flex-1 px-3 py-1.5 text-xs font-medium transition-colors ${
            tab === "logs"
              ? "text-foreground border-b-2 border-primary"
              : "text-muted-foreground hover:text-foreground"
          }`}
          onClick={() => setTab("logs")}
        >
          <History className="w-3 h-3 inline mr-1" />
          Logs
        </button>
        <Button
          size="sm"
          variant="ghost"
          className="h-auto px-2 text-muted-foreground hover:text-primary"
          onClick={() => setShowCreate(true)}
          title="Create alert"
        >
          <Plus className="w-3.5 h-3.5" />
        </Button>
      </div>

      {/* Tab content */}
      {tab === "alerts" ? (
        <AlertsTab instanceId={instanceId} onEdit={handleEdit} />
      ) : (
        <LogsTab instanceId={instanceId} />
      )}

      {/* Create alert dialog */}
      <CreateAlertDialog
        open={showCreate}
        onClose={handleClose}
        editAlert={editingAlert}
      />
    </div>
  );
}

// ── Alerts Tab ──────────────────────────────────────────────────────

function AlertsTab({
  instanceId,
  onEdit,
}: {
  instanceId: string;
  onEdit: (alert: Alert) => void;
}) {
  const { data: alerts = [], isLoading } = useAlerts();
  const { setChannelSymbol } = useWidget(instanceId);
  const deleteAlert = useDeleteAlert();
  const activateAlert = useActivateAlert();
  const pauseAlert = usePauseAlert();

  const sortedAlerts = useMemo(
    () =>
      [...alerts].sort((a, b) => {
        const statusOrder: Record<string, number> = {
          active: 0,
          paused: 1,
          triggered: 2,
          expired: 3,
        };
        const sa = statusOrder[a.status] ?? 9;
        const sb = statusOrder[b.status] ?? 9;
        if (sa !== sb) return sa - sb;
        return (b.created_at ?? "").localeCompare(a.created_at ?? "");
      }),
    [alerts],
  );

  const handleDelete = (alert: Alert) => {
    if (!window.confirm(`Delete alert "${alert.name || alert.symbol}"?`))
      return;
    deleteAlert.mutate(alert.id, {
      onSuccess: () => toast.success(`Alert deleted`),
      onError: () => toast.error(`Failed to delete alert`),
    });
  };

  const handleToggle = (alert: Alert) => {
    if (alert.status === "active") {
      pauseAlert.mutate(alert.id, {
        onSuccess: () => toast.success(`Alert paused`),
      });
    } else {
      activateAlert.mutate(alert.id, {
        onSuccess: () => toast.success(`Alert activated`),
      });
    }
  };

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center text-xs text-muted-foreground">
        Loading alerts...
      </div>
    );
  }

  if (alerts.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center p-4">
        <div className="w-full max-w-sm rounded-md border border-border bg-card/80 p-4 text-center space-y-3">
          <Bell className="w-6 h-6 text-muted-foreground mx-auto" />
          <p className="text-sm font-medium">No Alerts</p>
          <p className="text-xs text-muted-foreground">
            Create an alert from the chart or using a formula condition.
          </p>
        </div>
      </div>
    );
  }

  return (
    <ScrollArea className="flex-1">
      <div className="p-2 space-y-1">
        {sortedAlerts.map((alert) => {
          const isActive = alert.status === "active";
          const triggerLabel = _getTriggerLabel(alert);

          return (
            <div
              key={alert.id}
              onClick={() => setChannelSymbol(alert.symbol)}
              className={`flex items-center justify-between gap-2 rounded-md border px-3 py-2 transition-all cursor-pointer hover:border-primary/50 group ${
                isActive
                  ? "border-border bg-card/80 shadow-sm"
                  : "border-border/40 bg-card/40 opacity-60 hover:opacity-100"
              }`}
            >
              <div className="flex items-center gap-2.5 min-w-0">
                {isActive ? (
                  <Zap className="w-3.5 h-3.5 text-amber-500 shrink-0" />
                ) : (
                  <BellOff className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
                )}
                <div className="min-w-0">
                  <div className="flex items-center gap-1.5">
                    <span className="text-xs font-medium truncate">
                      {alert.name || alert.symbol}
                    </span>
                    <Badge
                      variant={isActive ? "secondary" : "outline"}
                      className={`text-[9px] px-1 py-0 h-4 ${STATUS_COLORS[alert.status] || ""}`}
                    >
                      {alert.status}
                    </Badge>
                  </div>
                  <div className="flex items-center gap-1 mt-0.5">
                    <span className="text-[10px] text-muted-foreground font-mono">
                      {alert.symbol}
                    </span>
                    <span className="text-[10px] text-muted-foreground">
                      •
                    </span>
                    <span className="text-[10px] text-muted-foreground truncate">
                      {triggerLabel}
                    </span>
                  </div>
                  <div className="flex items-center gap-1.5 mt-0.5">
                    <Clock className="w-2.5 h-2.5 text-muted-foreground" />
                    <span className="text-[9px] text-muted-foreground">
                      {FREQ_LABELS[alert.frequency] || alert.frequency}
                    </span>
                    {alert.trigger_count > 0 && (
                      <Badge
                        variant="outline"
                        className="text-[8px] px-1 py-0 h-3.5"
                      >
                        ×{alert.trigger_count}
                      </Badge>
                    )}
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-1 shrink-0">
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-6 w-6 p-0 text-muted-foreground hover:text-foreground"
                  onClick={() => handleToggle(alert)}
                  title={isActive ? "Pause" : "Activate"}
                >
                  {isActive ? (
                    <Pause className="w-3 h-3" />
                  ) : (
                    <Play className="w-3 h-3" />
                  )}
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-6 w-6 p-0 text-muted-foreground hover:text-foreground"
                  onClick={() => onEdit(alert)}
                  title="Edit alert"
                >
                  <Edit2 className="w-3 h-3" />
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-6 w-6 p-0 text-muted-foreground hover:text-destructive"
                  disabled={deleteAlert.isPending}
                  onClick={() => handleDelete(alert)}
                  title="Delete alert"
                >
                  <Trash2 className="w-3 h-3" />
                </Button>
              </div>
            </div>
          );
        })}
      </div>
    </ScrollArea>
  );
}

// ── Logs Tab ────────────────────────────────────────────────────────

function LogsTab({ instanceId }: { instanceId: string }) {
  const { data, isLoading } = useAlertLogs({ limit: 50 });
  const { setChannelSymbol } = useWidget(instanceId);
  const markRead = useMarkLogsRead();
  const deleteLog = useDeleteLog();
  const clearLogs = useClearLogs();

  const logs = data?.logs ?? [];
  const unreadCount = logs.filter((l) => !l.read).length;

  const handleMarkAllRead = () => {
    const unreadIds = logs.filter((l) => !l.read).map((l) => l.id);
    if (unreadIds.length === 0) return;
    markRead.mutate(unreadIds, {
      onSuccess: () => toast.success("All logs marked as read"),
    });
  };

  const handleClearAll = () => {
    if (!window.confirm("Delete all alert logs? This cannot be undone.")) return;
    clearLogs.mutate(undefined, {
      onSuccess: (res: any) => toast.success(`Cleared ${res.deleted} logs`),
      onError: () => toast.error("Failed to clear logs"),
    });
  };

  const handleDeleteLog = (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    deleteLog.mutate(id, {
      onSuccess: () => toast.success("Log deleted"),
    });
  };

  const handleLogClick = (log: any) => {
    // 1. Link symbol
    if (log.symbol) {
      setChannelSymbol(log.symbol);
    }
    // 2. Mark as read
    if (!log.read) {
      markRead.mutate([log.id]);
    }
  };

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center text-xs text-muted-foreground">
        Loading logs...
      </div>
    );
  }

  if (logs.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center p-4">
        <div className="w-full max-w-sm rounded-md border border-border bg-card/80 p-4 text-center space-y-3">
          <History className="w-6 h-6 text-muted-foreground mx-auto" />
          <p className="text-sm font-medium">No Alert Logs</p>
          <p className="text-xs text-muted-foreground">
            Triggered alerts will appear here.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col">
      <div className="px-2 py-1 border-b border-border flex items-center justify-between bg-muted/20">
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-muted-foreground font-medium uppercase tracking-tight">
            History
          </span>
          {unreadCount > 0 && (
            <Badge variant="secondary" className="text-[9px] px-1 h-3.5">
              {unreadCount} new
            </Badge>
          )}
        </div>
        <div className="flex items-center gap-1">
          {unreadCount > 0 && (
            <Button
              size="sm"
              variant="ghost"
              className="h-5 text-[9px] px-1.5 hover:text-primary"
              onClick={handleMarkAllRead}
            >
              Mark all read
            </Button>
          )}
          <Button
            size="sm"
            variant="ghost"
            className="h-5 w-5 p-0 text-muted-foreground hover:text-destructive"
            onClick={handleClearAll}
            title="Clear all logs"
          >
            <Trash2 className="w-2.5 h-2.5" />
          </Button>
        </div>
      </div>
      <ScrollArea className="flex-1">
        <div className="p-2 space-y-1">
          {logs.map((log) => (
            <div
              key={log.id}
              onClick={() => handleLogClick(log)}
              className={`group relative rounded-md border px-3 py-2 cursor-pointer transition-all ${
                log.read
                  ? "border-border/40 bg-card/20 grayscale-[0.5] opacity-70"
                  : "border-border bg-card shadow-sm hover:border-primary/50"
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-1.5 min-w-0">
                  {!log.read && (
                    <div className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse shrink-0" />
                  )}
                  <span className="text-xs font-semibold font-mono truncate">
                    {log.symbol}
                  </span>
                  {log.trigger_value != null && (
                    <span className="text-[10px] font-mono text-amber-500 font-medium">
                      {log.trigger_value.toFixed(2)}
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <span className="text-[9px] text-muted-foreground font-mono">
                    {_formatTime(log.triggered_at)}
                  </span>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="h-5 w-5 p-0 opacity-0 group-hover:opacity-100 transition-opacity hover:text-destructive"
                    onClick={(e) => handleDeleteLog(e, log.id)}
                  >
                    <Trash2 className="w-2.5 h-2.5" />
                  </Button>
                </div>
              </div>
              <p className="text-[10px] text-muted-foreground mt-0.5 line-clamp-1 group-hover:line-clamp-none transition-all">
                {log.message}
              </p>
            </div>
          ))}
        </div>
      </ScrollArea>
    </div>
  );
}

// ── Helpers ─────────────────────────────────────────────────────────

function _getTriggerLabel(alert: Alert): string {
  const cond = alert.trigger_condition;
  if (alert.alert_type === "formula") {
    return (cond as { formula?: string }).formula || "Formula";
  }
  const drawingType = (cond as { drawing_type?: string }).drawing_type || "Drawing";
  const triggerWhen = (cond as { trigger_when?: string }).trigger_when || "";
  return `${drawingType} ${triggerWhen.replace(/_/g, " ")}`;
}

function _formatTime(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) +
      " " +
      d.toLocaleDateString([], { month: "short", day: "numeric" });
  } catch {
    return iso;
  }
}
