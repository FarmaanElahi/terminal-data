import { useEffect } from "react";
import { terminalWS } from "@/lib/ws";
import { useAuthStore } from "@/stores/auth-store";
import type { WSMessage } from "@/types/ws";

/**
 * Hook to access the singleton WebSocket and subscribe to message types.
 */
export function useWebSocket() {
  const token = useAuthStore((s) => s.token);

  useEffect(() => {
    if (token && !terminalWS.isConnected) {
      terminalWS.connect(token);
    }
    return () => {
      // Don't disconnect on unmount — singleton stays alive
    };
  }, [token]);

  return {
    send: (msg: WSMessage) => terminalWS.send(msg),
    on: (type: string, handler: (msg: WSMessage) => void) =>
      terminalWS.on(type, handler),
    isConnected: terminalWS.isConnected,
  };
}
