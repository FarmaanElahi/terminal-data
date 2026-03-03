import { useCallback, useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { brokerApi, type BrokerStatus } from "@/lib/api";
import { terminalWS } from "@/lib/ws";
import { useAuthStore } from "@/stores/auth-store";
import { QUERY_KEYS } from "@/queries/query-keys";

export function useUpstoxStatus() {
  const qc = useQueryClient();
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);

  const query = useQuery({
    queryKey: QUERY_KEYS.upstoxStatus,
    queryFn: () => brokerApi.getUpstoxStatus().then((r) => r.data),
    enabled: isAuthenticated,
    staleTime: Infinity,
  });

  // Keep query data in sync with live WebSocket push updates
  useEffect(() => {
    return terminalWS.on("upstox_status", (msg) => {
      const payload = msg.p?.[0] as BrokerStatus | undefined;
      if (payload) {
        qc.setQueryData(QUERY_KEYS.upstoxStatus, payload);
      }
    });
  }, [qc]);

  const openLogin = useCallback(async () => {
    const { data } = await brokerApi.getUpstoxAuthUrl();
    const w = 500;
    const h = 700;
    const l = window.screenX + (window.outerWidth - w) / 2;
    const t = window.screenY + (window.outerHeight - h) / 2;
    window.open(
      data.url,
      "upstox-login",
      `width=${w},height=${h},left=${l},top=${t},menubar=no,toolbar=no,resizable=yes`,
    );
  }, []);

  return { ...query, openLogin };
}
