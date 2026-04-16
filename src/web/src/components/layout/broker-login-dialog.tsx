import { useEffect, useMemo, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { terminalWS } from "@/lib/ws";
import { useBrokers } from "@/hooks/use-brokers";
import type { BrokerInfo } from "@/types/broker";

export function BrokerLoginDialog() {
  const { data: brokers = [], openLogin } = useBrokers();
  const [requestedProviderId, setRequestedProviderId] = useState<string | null>(
    null,
  );

  // Only surface the dialog when the backend explicitly asks for a broker
  // login via the `broker_login_required` WS event. We used to also pop it
  // passively on load whenever any broker had `login_required: true`, which
  // prompted Zerodha login on every app load even though no feature depends
  // on it yet — removed.
  const activeBroker = useMemo((): BrokerInfo | null => {
    if (!requestedProviderId) return null;
    const requested =
      brokers.find((broker) => broker.provider_id === requestedProviderId) ??
      null;
    return requested?.login_required ? requested : null;
  }, [brokers, requestedProviderId]);

  useEffect(() => {
    return terminalWS.on("broker_login_required", (msg) => {
      const payload = msg.p?.[0] as Partial<BrokerInfo> | undefined;
      if (payload?.provider_id) {
        setRequestedProviderId(payload.provider_id);
      }
    });
  }, []);

  useEffect(() => {
    function onMessage(event: MessageEvent) {
      if (event.data?.type === "broker-login-success") {
        setRequestedProviderId(null);
      }
    }

    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, []);

  if (!activeBroker) return null;

  return (
    <Dialog
      open={Boolean(activeBroker)}
      onOpenChange={(nextOpen) => {
        if (nextOpen || !activeBroker) return;
        setRequestedProviderId(null);
      }}
    >
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Connect {activeBroker.display_name}</DialogTitle>
          <DialogDescription>
            Login to your {activeBroker.display_name} account to enable
            broker-backed features for {activeBroker.markets.join(", ")} markets.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter className="flex gap-2 sm:justify-start">
          <Button onClick={() => openLogin(activeBroker.provider_id)}>
            Login to {activeBroker.display_name}
          </Button>
          <Button
            variant="ghost"
            onClick={() => setRequestedProviderId(null)}
          >
            Later
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
