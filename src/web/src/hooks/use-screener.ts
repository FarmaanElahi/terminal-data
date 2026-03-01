import { useCallback, useEffect, useMemo, useRef } from "react";
import { useWebSocket } from "./use-websocket";
import { useWidgetState, useWidgetStateMerge } from "./use-widget-state";
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
  const mergeState = useWidgetStateMerge(instanceId);
  const lastUpdateThrottleRef = useRef<number>(0);

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

  // ─── Session Stability ────────────────────────────────────────────

  // Session ID stays stable for the lifetime of this hook instance (normally widget mount)
  const sessionId = useMemo(() => crypto.randomUUID(), []);

  // Track functional hash to avoid restarting on UI-only changes (width, name, etc.)
  const functionalHash = useMemo(() => {
    if (!listId || !columns) return null;
    const functionalCols = columns.map(
      ({
        name,
        visible,
        display_color,
        display_column_width,
        sort,
        display_numeric_positive_color,
        display_numeric_negative_color,
        display_numeric_prefix,
        display_numeric_suffix,
        display_numeric_show_positive_sign,
        ...f
      }) => f,
    );
    return JSON.stringify({ listId, columns: functionalCols });
  }, [listId, columns]);

  const isCreatedRef = useRef(false);
  const lastFunctionalHashRef = useRef<string | null>(null);

  // ─── Session Update Effect ────────────────────────────────────────
  useEffect(() => {
    if (!listId || !columns || !functionalHash) return;

    const timer = setTimeout(() => {
      if (!isCreatedRef.current) {
        // First initialization
        ws.send({
          m: "create_screener",
          p: [sessionId, { source: listId, columns }],
        });
        isCreatedRef.current = true;
        lastFunctionalHashRef.current = functionalHash;
        setIsLoading(true);
      } else if (functionalHash !== lastFunctionalHashRef.current) {
        // Parameters updated (formulas, timeframe, etc.) — reuse session
        ws.send({
          m: "modify_screener",
          p: [sessionId, { source: listId, columns }],
        });
        lastFunctionalHashRef.current = functionalHash;
        setIsLoading(true);
      }
    }, 100);

    return () => clearTimeout(timer);
  }, [listId, functionalHash, ws, sessionId, columns, setIsLoading]);

  // ─── Message Subscriptions ────────────────────────────────────────
  useEffect(() => {
    const unsubs = [
      ws.on("screener_filter", (msg: WSMessage) => {
        const [sid, tickerList, totalCount] = msg.p as [
          string,
          ScreenerFilterRow[],
          number,
        ];
        if (sid === sessionId) {
          // Full dataframe: Extract initial values from the filter rows
          const initialValues: ScreenerValues = {};
          tickerList.forEach((row) => {
            if (row.v) {
              Object.entries(row.v).forEach(([colId, val]) => {
                if (!initialValues[colId]) initialValues[colId] = [];
                initialValues[colId].push(val);
              });
            }
          });

          const patch: any = {
            tickers: tickerList,
            totalSymbols: totalCount ?? tickerList.length,
            isLoading: false,
          };

          if (Object.keys(initialValues).length > 0) {
            patch.values = initialValues;
          }

          // Throttle timestamp updates to 200ms
          const now = Date.now();
          if (now - lastUpdateThrottleRef.current > 200) {
            patch.lastUpdate = now;
            lastUpdateThrottleRef.current = now;
          }

          mergeState(patch);
        }
      }),

      ws.on("screener_values", (msg: WSMessage) => {
        const [sid, partialVals] = msg.p as [string, ScreenerValues];
        if (sid === sessionId) {
          const now = Date.now();
          const patch: any = {
            values: (prev: ScreenerValues) => ({
              ...prev,
              ...partialVals,
            }),
          };

          if (now - lastUpdateThrottleRef.current > 200) {
            patch.lastUpdate = now;
            lastUpdateThrottleRef.current = now;
          }

          mergeState(patch);
        }
      }),
    ];

    return () => unsubs.forEach((u) => u());
  }, [
    ws,
    sessionId,
    setTickers,
    setTotalSymbols,
    setIsLoading,
    setLastUpdate,
    setValues,
  ]);

  // ─── Cleanup Effect (Unmount only) ─────────────────────────────────
  useEffect(() => {
    return () => {
      if (isCreatedRef.current) {
        ws.send({ m: "destroy_screener", p: [sessionId] });
      }
    };
  }, [sessionId, ws]);

  const refresh = useCallback(() => {
    if (!isCreatedRef.current || !listId || !columns) return;
    ws.send({ m: "modify_screener", p: [sessionId, { source: listId, columns }] });
    setIsLoading(true);
  }, [ws, sessionId, listId, columns, setIsLoading]);

  return { tickers, values, isLoading, lastUpdate, totalSymbols, refresh };
}
