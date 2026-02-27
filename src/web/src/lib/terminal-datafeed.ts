import { terminalWS } from "@/lib/ws";
import type {
  WSMessage,
  SymbolResolvedData,
  ChartCandleData,
} from "@/types/ws";
import { useAuthStore } from "@/stores/auth-store";

// ─── Types ─────────────────────────────────────────────────────────

interface LibrarySymbolInfo {
  name: string;
  full_name: string;
  ticker: string;
  description: string;
  type: string;
  session: string;
  exchange: string;
  listed_exchange: string;
  timezone: string;
  format: string;
  pricescale: number;
  minmov: number;
  has_intraday: boolean;
  has_daily: boolean;
  has_weekly_and_monthly: boolean;
  supported_resolutions: string[];
  data_status: string;
  logo_urls?: string[];
}

interface Bar {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
}

interface DatafeedConfiguration {
  supported_resolutions: string[];
  exchanges: { value: string; name: string; desc: string }[];
  symbols_types: { name: string; value: string }[];
}

interface Subscription {
  onTick: (bar: Bar) => void;
  seriesId: string;
  listeners: string[]; // TV listenerGuids
}

// ─── Datafeed Implementation ───────────────────────────────────────

export class TerminalDatafeed {
  private _sessionId =
    typeof crypto !== "undefined" && crypto.randomUUID
      ? crypto.randomUUID()
      : Math.random().toString(36).substring(2);

  private _unsubscribeWS: (() => void) | null = null;

  // Track active subscriptions by series_id
  private _subscriptions = new Map<string, Subscription>();

  // Map listenerGuid -> seriesId for quick lookup during unsubscribe
  private _guidToSeriesId = new Map<string, string>();

  // Pending resolver and history promises
  private _resolveCallbacks = new Map<
    string,
    {
      resolve: (info: LibrarySymbolInfo) => void;
      reject: (err: string) => void;
    }
  >();
  private _historyCallbacks = new Map<
    string,
    {
      resolve: (bars: ChartCandleData[], noData: boolean) => void;
      reject: (error: string) => void;
    }
  >();
  private _lastBarTimes: Map<string, number> = new Map(); // series_id -> last timestamp

  constructor() {
    this._setupWSListener();
    // Initialize chart session on backend
    terminalWS.send({ m: "create_chart", p: [this._sessionId, null] });
  }

  private _setupWSListener() {
    const unsubs: (() => void)[] = [];

    unsubs.push(
      terminalWS.on("symbol_resolved", (msg: WSMessage) => {
        const [sid, data] = msg.p as [string, SymbolResolvedData];
        if (sid !== this._sessionId) return;

        const info: LibrarySymbolInfo = {
          name: data.name,
          full_name: data.ticker,
          ticker: data.ticker,
          description: data.description || data.name,
          type: data.type,
          session: data.session,
          exchange: data.exchange || "",
          listed_exchange: data.exchange || "",
          timezone: data.timezone as string,
          format: "price",
          pricescale: data.pricescale,
          minmov: data.minmov,
          has_intraday: data.has_intraday,
          has_daily: data.has_daily,
          has_weekly_and_monthly: data.has_weekly_and_monthly,
          supported_resolutions: data.supported_resolutions,
          data_status: "streaming",
          logo_urls: data.logo_urls,
        };

        const cb = this._resolveCallbacks.get(data.ticker);
        if (cb) {
          cb.resolve(info);
          this._resolveCallbacks.delete(data.ticker);
        }
      }),
    );

    unsubs.push(
      terminalWS.on("chart_series", (msg: WSMessage) => {
        const [sid, symbol, interval, candles, requestId, noData] = msg.p as [
          string,
          string,
          string,
          ChartCandleData[],
          string | null,
          boolean | undefined,
        ];
        if (sid !== this._sessionId) return;

        const bars: Bar[] = candles.map((c) => ({
          time: c.time,
          open: c.open,
          high: c.high,
          low: c.low,
          close: c.close,
          volume: c.volume,
        }));
        bars.sort((a, b) => a.time - b.time);

        // Find matching history request by requestId
        const targetId = requestId || `${symbol}-${interval}`;

        // Update last bar time to the latest from history
        if (bars.length > 0) {
          const lastTime = bars[bars.length - 1].time;
          this._lastBarTimes.set(targetId, lastTime);
        }

        const cb = this._historyCallbacks.get(targetId);

        console.log(
          `[Datafeed ${this._sessionId}] Received chart_series for ${targetId}. bars=${bars.length}, noData=${noData}, cb_found=${!!cb}`,
        );

        if (cb) {
          cb.resolve(candles, !!noData);
          this._historyCallbacks.delete(targetId);
        }
      }),
    );

    unsubs.push(
      terminalWS.on("chart_update", (msg: WSMessage) => {
        const [sid, symbol, c, seriesId] = msg.p as [
          string,
          string,
          ChartCandleData,
          string | null,
        ];
        if (sid !== this._sessionId) return;

        const bar: Bar = {
          time: c.time,
          open: c.open,
          high: c.high,
          low: c.low,
          close: c.close,
          volume: c.volume,
        };

        const targetId = seriesId || symbol; // Should ideally always have seriesId now

        const lastTime = this._lastBarTimes.get(targetId) || 0;
        if (bar.time < lastTime) {
          console.warn(
            `[Datafeed ${this._sessionId}] Out-of-order tick for ${targetId}. Tick: ${new Date(bar.time).toISOString()}, Last: ${new Date(lastTime).toISOString()}. Dropping.`,
          );
          return;
        }

        this._lastBarTimes.set(targetId, bar.time);

        const sub = this._subscriptions.get(targetId);
        if (sub) {
          sub.onTick(bar);
        }
      }),
    );

    this._unsubscribeWS = () => unsubs.forEach((u) => u());
  }

  onReady(callback: (config: DatafeedConfiguration) => void): void {
    setTimeout(() => {
      callback({
        supported_resolutions: [
          "1",
          "2",
          "3",
          "5",
          "10",
          "15",
          "20",
          "30",
          "45",
          "60",
          "120",
          "180",
          "240",
          "1D",
          "1W",
          "1M",
          "3M",
          "6M",
          "12M",
        ],
        exchanges: [
          { value: "NSE", name: "NSE", desc: "National Stock Exchange" },
          { value: "BSE", name: "BSE", desc: "Bombay Stock Exchange" },
          { value: "NASDAQ", name: "NASDAQ", desc: "NASDAQ" },
          { value: "NYSE", name: "NYSE", desc: "NYSE" },
        ],
        symbols_types: [{ name: "Stock", value: "stock" }],
      });
    }, 0);
  }

  async searchSymbols(
    userInput: string,
    exchange: string,
    _symbolType: string,
    onResult: (
      result: Array<{
        symbol: string;
        full_name: string;
        description: string;
        exchange: string;
        ticker: string;
        type: string;
      }>,
    ) => void,
  ): Promise<void> {
    const symbols = useAuthStore.getState().symbols;
    const query = userInput.toLowerCase();
    const market = exchange?.toLowerCase();

    const filtered = symbols.filter((s) => {
      const matchesText =
        s.ticker.toLowerCase().includes(query) ||
        s.name.toLowerCase().includes(query);
      const matchesMarket = !market || s.market.toLowerCase() === market;
      return matchesText && matchesMarket;
    });

    onResult(
      filtered.slice(0, 50).map((s) => ({
        symbol: s.ticker.split(":")[1] || s.ticker,
        full_name: s.ticker,
        description: s.name,
        exchange: s.ticker.split(":")[0],
        ticker: s.ticker,
        type: s.type || "stock",
      })),
    );
  }

  async resolveSymbol(
    symbolName: string,
    onResolve: (symbolInfo: LibrarySymbolInfo) => void,
    onError: (reason: string) => void,
  ): Promise<void> {
    // If we have it in our local symbol list, we can return it instantly
    // but the platform expects some fields like timezone and session
    // which might not be in our basic symbols list yet.
    // So we still request from backend but fall back if needed.

    // Register callback
    this._resolveCallbacks.set(symbolName, {
      resolve: onResolve,
      reject: onError,
    });

    terminalWS.send({ m: "resolve_symbol", p: [this._sessionId, symbolName] });

    // Timeout safety
    setTimeout(() => {
      if (this._resolveCallbacks.has(symbolName)) {
        this._resolveCallbacks.delete(symbolName);
        console.error(
          `[Datafeed ${this._sessionId}] Symbol resolution timeout for ${symbolName}`,
        );
        onError(`Symbol resolution timeout for ${symbolName}`);
      }
    }, 10000); // 10s for symbol resolve
  }

  async getBars(
    symbolInfo: LibrarySymbolInfo,
    resolution: string,
    periodParams: { from: number; to: number; firstDataRequest?: boolean },
    onResult: (bars: Bar[], meta: { noData?: boolean }) => void,
    onError: (reason: string) => void,
  ): Promise<void> {
    const symbol = symbolInfo.ticker || symbolInfo.full_name;
    const interval = this._mapResolution(resolution);
    const requestId = `history-${Math.random().toString(36).substring(2, 10)}`;

    const fromDate = new Date(periodParams.from * 1000)
      .toISOString()
      .split("T")[0];
    const toDate = new Date(periodParams.to * 1000).toISOString().split("T")[0];

    console.log(
      `[Datafeed ${this._sessionId}] getBars for ${symbol} @ ${resolution}. requestId=${requestId}, range=${fromDate} to ${toDate}`,
    );

    // Register callback
    this._historyCallbacks.set(requestId, {
      resolve: (candles, noDataFromServer) => {
        const bars: Bar[] = candles.map((c) => ({
          time: c.time,
          open: c.open,
          high: c.high,
          low: c.low,
          close: c.close,
          volume: c.volume,
        }));
        console.log(
          `[Datafeed ${this._sessionId}] Resolved getBars for ${requestId}. Bars: ${bars.length}, Server noData: ${noDataFromServer}`,
        );
        if (bars.length > 0) {
          console.log(
            `[Datafeed ${this._sessionId}] Sample bar for ${symbol}:`,
            bars[0],
          );
        }
        onResult(bars, { noData: noDataFromServer });
      },
      reject: onError,
    });

    terminalWS.send({
      m: "get_bar",
      p: [
        this._sessionId,
        {
          symbol,
          interval,
          from_date: fromDate,
          to_date: toDate,
          series_id: requestId,
        },
      ],
    });

    // Reset last bar time for this request to allow fresh data
    this._lastBarTimes.set(requestId, 0);

    // Timeout safety
    setTimeout(() => {
      if (this._historyCallbacks.has(requestId)) {
        this._historyCallbacks.delete(requestId);
        console.error(
          `[Datafeed ${this._sessionId}] Data load timeout for ${symbol} @ ${resolution}. requestId=${requestId}`,
        );
        onError("Data load timeout");
      }
    }, 15000); // Increased to 15s for multi-chunk history
  }

  subscribeBars(
    symbolInfo: LibrarySymbolInfo,
    resolution: string,
    onTick: (bar: Bar) => void,
    listenerGuid: string,
  ): void {
    const symbol = symbolInfo.ticker || symbolInfo.full_name;
    const interval = this._mapResolution(resolution);
    const seriesId = `${symbol}-${interval}`;

    this._guidToSeriesId.set(listenerGuid, seriesId);

    let sub = this._subscriptions.get(seriesId);
    if (!sub) {
      sub = {
        onTick,
        seriesId,
        listeners: [listenerGuid],
      };
      this._subscriptions.set(seriesId, sub);

      terminalWS.send({
        m: "subscribe_bar",
        p: [
          this._sessionId,
          {
            symbol,
            interval,
            series_id: seriesId,
          },
        ],
      });
    } else {
      // Add this listener to existing series subscription
      sub.listeners.push(listenerGuid);
      // Update onTick to latest (usually they use the same handler anyway)
      sub.onTick = onTick;
    }
  }

  unsubscribeBars(listenerGuid: string): void {
    const seriesId = this._guidToSeriesId.get(listenerGuid);
    if (!seriesId) return;

    this._guidToSeriesId.delete(listenerGuid);

    const sub = this._subscriptions.get(seriesId);
    if (!sub) return;

    // Remove listener
    sub.listeners = sub.listeners.filter((l) => l !== listenerGuid);

    // If no more listeners for this series, tell server to stop streaming
    if (sub.listeners.length === 0) {
      this._subscriptions.delete(seriesId);

      terminalWS.send({
        m: "unsubscribe_bar",
        p: [this._sessionId, seriesId],
      });
    }
  }

  destroy(): void {
    terminalWS.send({ m: "destroy_chart", p: [this._sessionId] });
    if (this._unsubscribeWS) {
      this._unsubscribeWS();
    }
    this._subscriptions.clear();
    this._guidToSeriesId.clear();
  }

  private _mapResolution(resolution: string): string {
    const map: Record<string, string> = {
      "1": "1m",
      "5": "5m",
      "15": "15m",
      "30": "30m",
      "60": "1h",
      "1D": "1d",
      D: "1d",
      "1W": "1w",
      "1M": "1M",
    };
    return map[resolution] || "1d";
  }
}
