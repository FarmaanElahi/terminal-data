import { useCallback, useMemo } from "react";
import { useBrokers } from "@/hooks/use-brokers";

export function useBrokerGate(capability: string, market: string) {
  const { data: brokers = [], defaults, openLogin } = useBrokers();

  const matching = useMemo(
    () =>
      brokers.filter(
        (broker) =>
          broker.capabilities.includes(capability) &&
          broker.markets.includes(market),
      ),
    [brokers, capability, market],
  );

  const connected = useMemo(
    () => matching.filter((broker) => broker.connected),
    [matching],
  );

  const selectedDefault = useMemo(
    () =>
      defaults.find(
        (item) => item.capability === capability && item.market === market,
      )?.provider_id ?? null,
    [defaults, capability, market],
  );

  const connectedBroker = useMemo(() => {
    if (connected.length === 0) return null;
    if (!selectedDefault) return connected[0];
    return (
      connected.find((broker) => broker.provider_id === selectedDefault) ??
      connected[0]
    );
  }, [connected, selectedDefault]);

  const promptConnect = useCallback(async () => {
    if (matching.length === 0) return;
    await openLogin(matching[0].provider_id);
  }, [matching, openLogin]);

  return {
    available: matching.length > 0,
    connected: connected.length > 0,
    needsLogin: matching.length > 0 && connected.length === 0,
    connectedBroker,
    promptConnect,
  };
}
