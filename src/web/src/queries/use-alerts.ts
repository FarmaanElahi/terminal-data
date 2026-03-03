import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { alertsApi } from "@/lib/api";
import { useAuthStore } from "@/stores/auth-store";
import { QUERY_KEYS } from "@/queries/query-keys";
import type {
  AlertCreateParams,
  AlertModifyParams,
  AlertDeleteParams,
} from "@/types/alert";

export function useAlertsQuery() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);

  return useQuery({
    queryKey: QUERY_KEYS.alerts,
    queryFn: () => alertsApi.list().then((r) => r.data),
    enabled: isAuthenticated,
    staleTime: 30_000,
  });
}

export function useCreateAlertMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: AlertCreateParams) =>
      alertsApi.create(data).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: QUERY_KEYS.alerts });
    },
  });
}

export function useModifyAlertMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...data }: AlertModifyParams & { id: string }) =>
      alertsApi.modify(id, data).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: QUERY_KEYS.alerts });
    },
  });
}

export function useDeleteAlertMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: AlertDeleteParams) =>
      alertsApi.remove(data).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: QUERY_KEYS.alerts });
    },
  });
}
