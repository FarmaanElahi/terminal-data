import { useCallback, useEffect } from "react";
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { brokerApi } from "@/lib/api";
import { terminalWS } from "@/lib/ws";
import { useAuthStore } from "@/stores/auth-store";
import type { BrokerDefault, BrokerInfo } from "@/types/broker";
import { QUERY_KEYS } from "@/queries/query-keys";

export function useBrokers() {
  const qc = useQueryClient();
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);

  const brokersQuery = useQuery({
    queryKey: QUERY_KEYS.brokers,
    queryFn: () => brokerApi.list().then((r) => r.data),
    enabled: isAuthenticated,
    staleTime: Infinity,
  });

  const defaultsQuery = useQuery({
    queryKey: QUERY_KEYS.brokerDefaults,
    queryFn: () => brokerApi.listDefaults().then((r) => r.data),
    enabled: isAuthenticated,
    staleTime: Infinity,
  });

  useEffect(() => {
    return terminalWS.on("broker_status", (msg) => {
      const payload = msg.p?.[0] as BrokerInfo[] | Partial<BrokerInfo> | undefined;
      if (!payload) return;

      if (Array.isArray(payload)) {
        qc.invalidateQueries({ queryKey: QUERY_KEYS.brokers });
        return;
      }

      const providerId = payload.provider_id;
      if (!providerId) return;

      qc.setQueryData<BrokerInfo[]>(QUERY_KEYS.brokers, (current) => {
        if (!current || current.length === 0) return current;
        return current.map((broker) =>
          broker.provider_id === providerId ? { ...broker, ...payload } : broker,
        );
      });
      qc.invalidateQueries({ queryKey: QUERY_KEYS.brokers });
    });
  }, [qc]);

  const setDefaultMutation = useMutation({
    mutationFn: (data: BrokerDefault) => brokerApi.setDefault(data),
    onSuccess: (_, vars) => {
      qc.setQueryData<BrokerDefault[]>(QUERY_KEYS.brokerDefaults, (current) => {
        const items = current ?? [];
        const others = items.filter(
          (item) =>
            !(
              item.capability === vars.capability &&
              item.market === vars.market
            ),
        );
        return [...others, vars];
      });
    },
  });

  const removeAccountMutation = useMutation({
    mutationFn: ({
      providerId,
      credentialId,
    }: {
      providerId: string;
      credentialId: string;
    }) => brokerApi.removeAccount(providerId, credentialId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: QUERY_KEYS.brokers });
    },
  });

  const openLogin = useCallback(async (providerId: string) => {
    const { data } = await brokerApi.getAuthUrl(providerId);
    const w = 500;
    const h = 700;
    const l = window.screenX + (window.outerWidth - w) / 2;
    const t = window.screenY + (window.outerHeight - h) / 2;
    window.open(
      data.url,
      `broker-login-${providerId}`,
      `width=${w},height=${h},left=${l},top=${t},menubar=no,toolbar=no,resizable=yes`,
    );
  }, []);

  return {
    ...brokersQuery,
    defaults: defaultsQuery.data ?? [],
    defaultsLoading: defaultsQuery.isLoading,
    setDefault: setDefaultMutation.mutateAsync,
    isSettingDefault: setDefaultMutation.isPending,
    removeAccount: removeAccountMutation.mutateAsync,
    isRemovingAccount: removeAccountMutation.isPending,
    openLogin,
  };
}
