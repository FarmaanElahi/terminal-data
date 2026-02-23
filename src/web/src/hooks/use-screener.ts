import { useEffect, useCallback } from "react";
import { useWebSocket } from "./use-websocket";
import { useScreenerStore } from "@/stores/screener-store";
import type { ScreenerFilterRow, ScreenerValues, WSMessage } from "@/types/ws";

/**
 * Hook that manages a screener WebSocket session lifecycle.
 * Creates session on mount, subscribes to updates, cleans up on unmount.
 */
export function useScreener(listId: string | null, columnSetId: string | null) {
  const ws = useWebSocket();
  const {
    tickers,
    values,
    isLoading,
    lastUpdate,
    setSession,
    setTickers,
    setValues,
    updateValue,
    reset,
  } = useScreenerStore();

  const createSession = useCallback(() => {
    if (!listId || !columnSetId) return;

    const sessionId = crypto.randomUUID();
    setSession(sessionId);

    ws.send({
      m: "create_screener",
      p: [sessionId, { source: listId, column_set_id: columnSetId }],
    });

    return sessionId;
  }, [listId, columnSetId, ws, setSession]);

  useEffect(() => {
    const sessionId = createSession();
    if (!sessionId) return;

    const unsubs = [
      ws.on("screener_session_created", (_msg: WSMessage) => {
        // Session confirmed
      }),

      ws.on("screener_filter", (msg: WSMessage) => {
        const [sid, tickerList] = msg.p as [string, ScreenerFilterRow[]];
        if (sid === sessionId) {
          setTickers(tickerList);
        }
      }),

      ws.on("screener_values", (msg: WSMessage) => {
        const [sid, vals] = msg.p as [string, ScreenerValues];
        if (sid === sessionId) {
          setValues(vals);
        }
      }),

      ws.on("screener_values_update", (msg: WSMessage) => {
        const [sid, ticker, updates] = msg.p as [
          string,
          string,
          Record<string, unknown>,
        ];
        if (sid === sessionId) {
          updateValue(ticker, updates);
        }
      }),
    ];

    return () => {
      unsubs.forEach((unsub) => unsub());
      ws.send({ m: "destroy_screener", p: [sessionId] });
      reset();
    };
  }, [listId, columnSetId]);

  return { tickers, values, isLoading, lastUpdate };
}
