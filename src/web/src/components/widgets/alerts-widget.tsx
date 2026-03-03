import { useMemo } from "react";
import {
  Bell,
  BellOff,
  Trash2,
  AlertCircle,
  ArrowUpRight,
  ArrowDownRight,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { WidgetProps } from "@/types/layout";
import { useAlertsQuery, useDeleteAlertMutation } from "@/queries/use-alerts";
import { useBrokerGate } from "@/hooks/use-broker-gate";
import { toast } from "sonner";

const OPERATOR_LABELS: Record<
  string,
  { label: string; icon: typeof ArrowUpRight }
> = {
  ">=": { label: "≥", icon: ArrowUpRight },
  ">": { label: ">", icon: ArrowUpRight },
  "<=": { label: "≤", icon: ArrowDownRight },
  "<": { label: "<", icon: ArrowDownRight },
  "==": { label: "=", icon: AlertCircle },
};

export function AlertsWidget(props: WidgetProps) {
  void props;
  const { data: alerts = [], isLoading } = useAlertsQuery();
  const deleteAlert = useDeleteAlertMutation();
  const { needsLogin, promptConnect } = useBrokerGate("alerts", "india");

  const sortedAlerts = useMemo(
    () =>
      [...alerts].sort((a, b) => {
        // enabled first, then by created_at desc
        if (a.status !== b.status) return a.status === "enabled" ? -1 : 1;
        return (b.created_at ?? "").localeCompare(a.created_at ?? "");
      }),
    [alerts],
  );

  const handleDelete = (uuid: string, providerId: string, name: string) => {
    const confirmed = window.confirm(`Delete alert "${name}"?`);
    if (!confirmed) return;

    deleteAlert.mutate(
      { provider_id: providerId, uuids: [uuid] },
      {
        onSuccess: () => toast.success(`Alert "${name}" deleted`),
        onError: () => toast.error(`Failed to delete alert "${name}"`),
      },
    );
  };

  if (isLoading) {
    return (
      <div className="h-full flex items-center justify-center text-xs text-muted-foreground">
        Loading alerts...
      </div>
    );
  }

  if (needsLogin) {
    return (
      <div className="h-full flex items-center justify-center p-4">
        <div className="w-full max-w-sm rounded-md border border-border bg-card/80 p-4 text-center space-y-3">
          <div className="flex items-center justify-center">
            <Bell className="w-6 h-6 text-muted-foreground" />
          </div>
          <p className="text-sm font-medium">Broker Login Required</p>
          <p className="text-xs text-muted-foreground">
            Connect a broker account that supports alerts to manage your price
            alerts.
          </p>
          <Button
            size="sm"
            variant="outline"
            onClick={() => void promptConnect()}
            className="gap-1"
          >
            Connect Broker
          </Button>
        </div>
      </div>
    );
  }

  if (alerts.length === 0) {
    return (
      <div className="h-full flex items-center justify-center p-4">
        <div className="w-full max-w-sm rounded-md border border-border bg-card/80 p-4 text-center space-y-3">
          <div className="flex items-center justify-center">
            <Bell className="w-6 h-6 text-muted-foreground" />
          </div>
          <p className="text-sm font-medium">No Alerts</p>
          <p className="text-xs text-muted-foreground">
            Right-click on a chart to add an alert at any price level.
          </p>
        </div>
      </div>
    );
  }

  return (
    <ScrollArea className="h-full">
      <div className="p-2 space-y-1">
        {sortedAlerts.map((alert) => {
          const op = OPERATOR_LABELS[alert.operator] ?? {
            label: alert.operator,
            icon: AlertCircle,
          };
          const isEnabled = alert.status === "enabled";
          const symbol = `${alert.lhs_exchange}:${alert.lhs_tradingsymbol}`;

          return (
            <div
              key={alert.uuid}
              className={`flex items-center justify-between gap-2 rounded-md border px-3 py-2 transition-colors ${
                isEnabled
                  ? "border-border bg-card/80"
                  : "border-border/40 bg-card/40 opacity-60"
              }`}
            >
              <div className="flex items-center gap-2.5 min-w-0">
                {isEnabled ? (
                  <Bell className="w-3.5 h-3.5 text-amber-500 shrink-0" />
                ) : (
                  <BellOff className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
                )}
                <div className="min-w-0">
                  <div className="flex items-center gap-1.5">
                    <span className="text-xs font-medium truncate">
                      {alert.name || symbol}
                    </span>
                    <Badge
                      variant={isEnabled ? "secondary" : "outline"}
                      className="text-[9px] px-1 py-0 h-4"
                    >
                      {alert.status}
                    </Badge>
                  </div>
                  <div className="flex items-center gap-1 mt-0.5">
                    <span className="text-[10px] text-muted-foreground font-mono">
                      {symbol}
                    </span>
                    <span className="text-[10px] text-muted-foreground">
                      {op.label}
                    </span>
                    {alert.rhs_type === "constant" &&
                    alert.rhs_constant != null ? (
                      <span className="text-[10px] font-medium font-mono text-amber-500">
                        {alert.rhs_constant}
                      </span>
                    ) : (
                      <span className="text-[10px] text-muted-foreground font-mono">
                        {alert.rhs_exchange}:{alert.rhs_tradingsymbol}
                      </span>
                    )}
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-1 shrink-0">
                {alert.alert_count > 0 && (
                  <Badge variant="outline" className="text-[9px] px-1 py-0 h-4">
                    ×{alert.alert_count}
                  </Badge>
                )}
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-6 w-6 p-0 text-muted-foreground hover:text-destructive"
                  disabled={deleteAlert.isPending}
                  onClick={() =>
                    handleDelete(
                      alert.uuid,
                      alert.provider_id,
                      alert.name || symbol,
                    )
                  }
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
