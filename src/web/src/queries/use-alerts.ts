/**
 * React Query hooks for the local alert system.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { alertsApi, notificationsApi } from "@/lib/api";
import type {
  Alert,
  AlertCreateParams,
  AlertUpdateParams,
  AlertLog,
  AlertLogsResponse,
  NotificationChannel,
  NotificationChannelCreate,
} from "@/types/alert";

// ── Query Keys ─────────────────────────────────────────────────────

export const alertKeys = {
  all: ["alerts"] as const,
  list: (filters?: { status?: string; symbol?: string }) =>
    ["alerts", "list", filters] as const,
  logs: (params?: {
    alert_id?: string;
    symbol?: string;
    limit?: number;
    offset?: number;
  }) => ["alerts", "logs", params] as const,
  channels: ["notifications", "channels"] as const,
};

// ── Alert Queries ──────────────────────────────────────────────────

export function useAlerts(filters?: { status?: string; symbol?: string }) {
  return useQuery({
    queryKey: alertKeys.list(filters),
    queryFn: () => alertsApi.list(filters).then((r) => r.data),
  });
}

export function useAlertLogs(params?: {
  alert_id?: string;
  symbol?: string;
  limit?: number;
  offset?: number;
}) {
  return useQuery({
    queryKey: alertKeys.logs(params),
    queryFn: () => alertsApi.logs(params).then((r) => r.data),
    refetchInterval: 30_000, // refresh logs every 30s
  });
}

export function useNotificationChannels() {
  return useQuery({
    queryKey: alertKeys.channels,
    queryFn: () => notificationsApi.listChannels().then((r) => r.data),
  });
}

// ── Alert Mutations ────────────────────────────────────────────────

export function useCreateAlert() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: AlertCreateParams) =>
      alertsApi.create(data).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: alertKeys.all });
    },
  });
}

export function useUpdateAlert() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: AlertUpdateParams }) =>
      alertsApi.update(id, data).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: alertKeys.all });
    },
  });
}

export function useDeleteAlert() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => alertsApi.remove(id).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: alertKeys.all });
    },
  });
}

export function useActivateAlert() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => alertsApi.activate(id).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: alertKeys.all });
    },
  });
}

export function usePauseAlert() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => alertsApi.pause(id).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: alertKeys.all });
    },
  });
}

export function useDeleteAlertsByDrawing() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (drawingId: string) =>
      alertsApi.removeByDrawing(drawingId).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: alertKeys.all });
    },
  });
}

export function useMarkLogsRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (logIds: string[]) =>
      alertsApi.markLogsRead(logIds).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["alerts", "logs"] });
    },
  });
}

export function useDeleteLog() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => alertsApi.removeLog(id).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["alerts", "logs"] });
    },
  });
}

export function useClearLogs() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => alertsApi.clearLogs().then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["alerts", "logs"] });
    },
  });
}

// ── Notification Channel Mutations ─────────────────────────────────

export function useCreateChannel() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: NotificationChannelCreate) =>
      notificationsApi.createChannel(data).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: alertKeys.channels });
    },
  });
}

export function useDeleteChannel() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      notificationsApi.deleteChannel(id).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: alertKeys.channels });
    },
  });
}
