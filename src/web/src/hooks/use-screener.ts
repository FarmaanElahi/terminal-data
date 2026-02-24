import { useEffect, useCallback, useRef } from "react";
import { useWebSocket } from "./use-websocket";
import { useWidgetState } from "./use-widget-state";
import type { ScreenerFilterRow, ScreenerValues, WSMessage } from "@/types/ws";

import type { ColumnDef } from "@/types/models";

/**
 * Hook that manages a screener WebSocket session lifecycle.
 *
 * Uses the framework-level useWidgetState to persist data across remounts.
 * When the widget remounts (tab switch, float, dock, split), the cached
 * data is instantly restored and only a new WS session is created if the
 * params (listId, columns) actually changed.
 */
export function useScreener(
  instanceId: string,
  listId: string | null,
  columns: ColumnDef[] | null,
) {
  const ws = useWebSocket();

  // ─── Framework-level persistent state ─────────────────────────────
  const [tickers, setTickers] = useWidgetState<ScreenerFilterRow[]>(
    instanceId,
    "tickers",
    [],
  );
  const [values, setValues] = useWidgetState<ScreenerValues>(
    instanceId,
    "values",
    {},
  );
  const [isLoading, setIsLoading] = useWidgetState<boolean>(
    instanceId,
    "isLoading",
    true,
  );
  const [lastUpdate, setLastUpdate] = useWidgetState<number | null>(
    instanceId,
    "lastUpdate",
    null,
  );
  const [totalSymbols, setTotalSymbols] = useWidgetState<number>(
    instanceId,
    "totalSymbols",
    0,
  );
  // Track active session ID across re-renders
  const sessionRef = useRef<string | null>(null);

  // Hash columns to detect real changes, ignore reference changes
  const columnsHash = columns ? JSON.stringify(columns) : null;
  const paramsKey = listId && columnsHash ? `${listId}:${columnsHash}` : null;

  // Track what we actually launched through the socket
  const activeParamsRef = useRef<string | null>(null);

  // Use a ref for the latest columns to avoid createSession stability issues
  const columnsRef = useRef(columns);
  useEffect(() => {
    columnsRef.current = columns;
  }, [columnsHash]);

  const createSession = useCallback(() => {
    if (!listId || !columnsRef.current || !paramsKey) return;
    if (activeParamsRef.current === paramsKey) return;

    const sessionId = crypto.randomUUID();
    sessionRef.current = sessionId;
    activeParamsRef.current = paramsKey;
    setIsLoading(true);

    ws.send({
      m: "create_screener",
      p: [sessionId, { source: listId, columns: columnsRef.current }],
    });

    return sessionId;
  }, [listId, ws, setIsLoading, paramsKey]);

  useEffect(() => {
    if (!listId || !columnsHash || !paramsKey) {
      // If we had a session, it will be destroyed by the cleanup of the previous effect
      // or we can explicitly clear it if needed.
      return;
    }

    // Small debounce to avoid flapping during boot/rapid switches
    const timer = setTimeout(() => {
      const sessionId = createSession();
      if (!sessionId) return;

      const unsubs = [
        ws.on("screener_filter", (msg: WSMessage) => {
          const [sid, tickerList, totalCount] = msg.p as [
            string,
            ScreenerFilterRow[],
            number,
          ];
          if (sid === sessionId) {
            setTickers(tickerList);
            setTotalSymbols(totalCount ?? tickerList.length);
            setIsLoading(false);
            setLastUpdate(Date.now());
          }
        }),

        ws.on("screener_values", (msg: WSMessage) => {
          const [sid, partialVals] = msg.p as [string, ScreenerValues];
          if (sid === sessionId) {
            setValues((prev) => ({
              ...prev,
              ...partialVals,
            }));
            setLastUpdate(Date.now());
          }
        }),
      ];

      sessionRef.current = sessionId; // Ensure ref is set for cleanup

      // Store unsubs in a local variable for the cleanup closure
      return () => unsubs.forEach((u) => u());
    }, 100);

    return () => {
      clearTimeout(timer);
      if (sessionRef.current) {
        ws.send({ m: "destroy_screener", p: [sessionRef.current] });
        sessionRef.current = null;
        activeParamsRef.current = null;
      }
    };
  }, [paramsKey, listId, columnsHash, createSession, ws]);

  return { tickers, values, isLoading, lastUpdate, totalSymbols };
}
