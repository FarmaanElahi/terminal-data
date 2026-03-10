/**
 * Hook that listens for alert_triggered and alert_status_changed WebSocket
 * messages and displays toast notifications + invalidates React Query cache.
 *
 * Mount this once near the root of the app (e.g. in App.tsx or a layout).
 */

import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useWebSocket } from "./use-websocket";
import { alertKeys } from "@/queries/use-alerts";
import { toast } from "sonner";
import type { WSMessage } from "@/types/ws";
import type { AlertTriggeredPayload, AlertStatusChangedPayload } from "@/types/alert";

import { playBeep } from "@/lib/audio";

export function useAlertNotifications() {
  const ws = useWebSocket();
  const qc = useQueryClient();

  useEffect(() => {
    const unsubs = [
      ws.on("alert_triggered", (msg: WSMessage) => {
        const payload = (msg.p as unknown[])?.[0] as AlertTriggeredPayload | undefined;
        if (!payload) return;

        // Better message formatting
        const symbol = payload.symbol.includes(":")
          ? payload.symbol.split(":")[1]
          : payload.symbol;
        const title = `🔔 ${symbol} - ${payload.alert_name || "Alert"}`;
        const description = `${payload.message} (Value: ${payload.trigger_value?.toFixed(2)})`;

        // Show toast
        toast.info(title, {
          description,
          duration: 10000,
        });

        // Play sound if enabled
        if (payload.alert_sound) {
          playBeep(payload.alert_sound);
        }

        // Invalidate alert queries to refresh lists and logs
        qc.invalidateQueries({ queryKey: alertKeys.all });
        qc.invalidateQueries({ queryKey: ["alerts", "logs"] });
      }),

      ws.on("alert_status_changed", (msg: WSMessage) => {
        const payload = (msg.p as unknown[])?.[0] as AlertStatusChangedPayload | undefined;
        if (!payload) return;

        // Show toast for status changes (e.g. auto-deactivation)
        toast.info(`Alert ${payload.new_status}`, {
          description: `"${payload.alert_name}" is now ${payload.new_status}`,
          duration: 5000,
        });

        // Refresh alert list
        qc.invalidateQueries({ queryKey: alertKeys.all });
      }),
    ];

    return () => unsubs.forEach((u) => u());
  }, [ws, qc]);
}
