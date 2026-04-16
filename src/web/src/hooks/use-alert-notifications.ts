/**
 * Hook that listens for alert_triggered and alert_status_changed WebSocket
 * messages and:
 *   1. Shows a Sonner toast (always)
 *   2. Fires a browser system Notification (when permission granted + tab hidden)
 *   3. Persists to the notification center store (notifications-store.ts)
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
import { useNotificationsStore } from "@/stores/notifications-store";

function fireBrowserNotification(
  title: string,
  body: string,
  tag: string,
  permission: NotificationPermission,
) {
  // Only fire when:
  // - Permission is granted
  // - The tab is not currently visible (avoid doubling up with the toast)
  if (permission !== "granted") return;
  if (!document.hidden) return;
  if (!("Notification" in window)) return;
  try {
    new Notification(title, { body, tag, icon: "/favicon.ico" });
  } catch {
    // Silently ignore (e.g. service worker not registered in some browsers)
  }
}

export function useAlertNotifications() {
  const ws = useWebSocket();
  const qc = useQueryClient();
  const { addNotification, browserPermission } = useNotificationsStore();

  useEffect(() => {
    const unsubs = [
      ws.on("alert_triggered", (msg: WSMessage) => {
        const payload = (msg.p as unknown[])?.[0] as AlertTriggeredPayload | undefined;
        if (!payload) return;

        const symbol = payload.symbol.includes(":")
          ? payload.symbol.split(":")[1]
          : payload.symbol;
        const title = `🔔 ${symbol} - ${payload.alert_name || "Alert"}`;
        const description = `${payload.message} (Value: ${payload.trigger_value?.toFixed(2)})`;

        // 1. Toast
        toast.info(title, { description, duration: Infinity });

        // 2. Browser system notification
        fireBrowserNotification(
          `${symbol} — ${payload.alert_name || "Alert"}`,
          description,
          `alert-${payload.alert_id}`,
          browserPermission,
        );

        // 3. Notification center
        addNotification({
          id: `alert-${payload.alert_id}-${Date.now()}`,
          type: "alert_triggered",
          title,
          description,
          timestamp: payload.timestamp ?? new Date().toISOString(),
        });

        // 4. Sound
        if (payload.alert_sound) {
          playBeep(payload.alert_sound);
        }

        // 5. Invalidate query cache
        qc.invalidateQueries({ queryKey: alertKeys.all });
        qc.invalidateQueries({ queryKey: ["alerts", "logs"] });
      }),

      ws.on("alert_status_changed", (msg: WSMessage) => {
        const payload = (msg.p as unknown[])?.[0] as AlertStatusChangedPayload | undefined;
        if (!payload) return;

        const title = `Alert ${payload.new_status}`;
        const description = `"${payload.alert_name}" is now ${payload.new_status}`;

        // 1. Toast
        toast.info(title, { description, duration: 5000 });

        // 2. Browser system notification
        fireBrowserNotification(
          title,
          description,
          `alert-status-${payload.alert_id}`,
          browserPermission,
        );

        // 3. Notification center
        addNotification({
          id: `alert-status-${payload.alert_id}-${Date.now()}`,
          type: "alert_status_changed",
          title,
          description,
          timestamp: payload.timestamp ?? new Date().toISOString(),
        });

        // 4. Invalidate query cache
        qc.invalidateQueries({ queryKey: alertKeys.all });
      }),
    ];

    return () => unsubs.forEach((u) => u());
  }, [ws, qc, addNotification, browserPermission]);
}
