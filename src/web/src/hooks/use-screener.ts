import { useEffect, useCallback, useRef } from "react";
import { useWebSocket } from "./use-websocket";
import { useWidgetState } from "./use-widget-state";
import type { ScreenerFilterRow, ScreenerValues, WSMessage } from "@/types/ws";

/**
 * Hook that manages a screener WebSocket session lifecycle.
 *
 * Uses the framework-level useWidgetState to persist data across remounts.
 * When the widget remounts (tab switch, float, dock, split), the cached
 * data is instantly restored and only a new WS session is created if the
 * params (listId, columnSetId) actually changed.
 */
export function useScreener(
  instanceId: string,
  listId: string | null,
  columnSetId: string | null,
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
  // Track params that last created a session, so we only re-create if they change
  const [cachedParams, setCachedParams] = useWidgetState<string | null>(
    instanceId,
    "cachedParams",
    null,
  );
  // Track active session ID across re-renders
  const sessionRef = useRef<string | null>(null);
  const paramsKey = listId && columnSetId ? `${listId}:${columnSetId}` : null;

  const createSession = useCallback(() => {
    if (!listId || !columnSetId) return;

    const sessionId = crypto.randomUUID();
    sessionRef.current = sessionId;
    setIsLoading(true);

    ws.send({
      m: "create_screener",
      p: [sessionId, { source: listId, column_set_id: columnSetId }],
    });

    // Remember which params this session is for
    setCachedParams(paramsKey);

    return sessionId;
  }, [listId, columnSetId, ws, setIsLoading, setCachedParams, paramsKey]);

  useEffect(() => {
    // If we already have cached data for the same params, skip re-creating the session
    // but still set up listeners in case the server sends updates
    const needsNewSession = paramsKey !== cachedParams;

    if (!needsNewSession && tickers.length > 0) {
      // Data is already cached — no need to create a new session
      setIsLoading(false);
      return;
    }

    if (!listId || !columnSetId) return;

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
          setIsLoading(false);
          setLastUpdate(Date.now());
        }
      }),

      ws.on("screener_values", (msg: WSMessage) => {
        const [sid, vals] = msg.p as [string, ScreenerValues];
        if (sid === sessionId) {
          setValues(vals);
          setLastUpdate(Date.now());
        }
      }),
    ];

    return () => {
      unsubs.forEach((unsub) => unsub());
      if (sessionRef.current) {
        ws.send({ m: "destroy_screener", p: [sessionRef.current] });
      }
      // DON'T clear cached data — that's the whole point of useWidgetState
    };
  }, [listId, columnSetId]);

  return { tickers, values, isLoading, lastUpdate };
}
