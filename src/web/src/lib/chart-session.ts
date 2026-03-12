import { terminalWS } from "@/lib/ws";
import type {
  WSMessage,
  SymbolResolvedData,
  ChartCandleData,
} from "@/types/ws";
import { v4 as uuidv4 } from "uuid";

// ─── Types and Interfaces ─────────────────────────────────────────

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

type OnTickCallback = (bar: Bar) => void;

interface Subscription {
  onTick: OnTickCallback;
  symbol: string;
  interval: string;
  seriesId: string;
  listeners: Set<string>; // TV listenerGuids
}

interface PendingHistoryRequest {
  resolve: (bars: ChartCandleData[], noData: boolean) => void;
  reject: (error: string) => void;
  symbol: string;
  interval: string;
  requestId: string;
}

interface PendingResolveRequest {
  resolve: (info: LibrarySymbolInfo) => void;
  reject: (err: string) => void;
  symbol: string;
}

// ─── ChartSession Implementation ──────────────────────────────────

export class ChartSession {
  private _sessionId: string;
  private _isCreated = false;
  private _isRecovering = false;
  private _createPromise: Promise<void> | null = null;
  private _createResolvers: Array<() => void> = [];

  private _subscriptions = new Map<string, Subscription>(); // seriesId -> Subscription
  private _guidToSeriesId = new Map<string, string>(); // listenerGuid -> seriesId

  private _resolveCallbacks = new Map<string, PendingResolveRequest>(); // symbol -> Request
  private _historyCallbacks = new Map<string, PendingHistoryRequest>(); // requestId -> Request

  private _unsubs: Array<() => void> = [];

  constructor(sessionId?: string) {
    this._sessionId = sessionId || uuidv4();

    this._setupWSHandlers();
    void this.ensureSession();
  }

  get sessionId(): string {
    return this._sessionId;
  }

  private _setupWSHandlers() {
    this._unsubs.push(
      terminalWS.on("chart_session_created", (msg: WSMessage) => {
        const [sid] = (msg.p ?? []) as [string];
        if (sid !== this._sessionId) return;

        console.log(`[ChartSession ${this._sessionId}] Session created on backend`);
        this._isCreated = true;
        const resolvers = [...this._createResolvers];
        this._createResolvers = [];
        resolvers.forEach((resolve) => resolve());
      }),
    );

    this._unsubs.push(
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

    this._unsubs.push(
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

        const targetId = requestId || `${symbol}-${interval}`;
        const cb = this._historyCallbacks.get(targetId);

        if (cb) {
          console.log(`[ChartSession ${this._sessionId}] Received chart_series for ${targetId}. bars=${candles.length}`);
          cb.resolve(candles, !!noData);
          this._historyCallbacks.delete(targetId);
        }
      }),
    );

    this._unsubs.push(
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

        const targetId = seriesId || symbol;
        const sub = this._subscriptions.get(targetId);
        if (sub) {
          sub.onTick(bar);
        }
      }),
    );

    this._unsubs.push(
      terminalWS.on("error", (msg: WSMessage) => {
        const errText = String((msg.p ?? [""])[0] ?? "");
        if (
          errText.includes("Chart session") &&
          errText.includes(this._sessionId) &&
          errText.includes("not found")
        ) {
          console.warn(`[ChartSession ${this._sessionId}] Session lost on backend, recovering...`);
          this._isCreated = false;
          void this.recoverSession();
        }
      }),
    );
  }

  async resolveSymbol(symbol: string): Promise<LibrarySymbolInfo> {
    await this.ensureSession();

    return new Promise((resolve, reject) => {
      this._resolveCallbacks.set(symbol, { resolve, reject, symbol });

      terminalWS.send({ m: "resolve_symbol", p: [this._sessionId, symbol] });

      // Timeout safety
      setTimeout(() => {
        if (this._resolveCallbacks.has(symbol)) {
          this._resolveCallbacks.delete(symbol);
          reject(`Symbol resolution timeout for ${symbol}`);
        }
      }, 10000);
    });
  }

  async getBars(
    symbol: string,
    interval: string,
    fromDate: string,
    toDate: string,
    requestId: string,
  ): Promise<{ candles: ChartCandleData[]; noData: boolean }> {
    await this.ensureSession();

    return new Promise((resolve, reject) => {
      this._historyCallbacks.set(requestId, {
        resolve: (candles, noData) => resolve({ candles, noData }),
        reject,
        symbol,
        interval,
        requestId,
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

      // Timeout safety
      setTimeout(() => {
        if (this._historyCallbacks.has(requestId)) {
          this._historyCallbacks.delete(requestId);
          reject("Data load timeout");
        }
      }, 15000);
    });
  }

  subscribeBars(
    symbol: string,
    interval: string,
    onTick: OnTickCallback,
    listenerGuid: string,
  ): void {
    const seriesId = `${symbol}-${interval}`;
    this._guidToSeriesId.set(listenerGuid, seriesId);

    let sub = this._subscriptions.get(seriesId);
    if (!sub) {
      sub = {
        onTick,
        symbol,
        interval,
        seriesId,
        listeners: new Set([listenerGuid]),
      };
      this._subscriptions.set(seriesId, sub);

      void this.ensureSession().then(() => {
        if (!this._subscriptions.has(seriesId)) return;
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
      });
    } else {
      sub.listeners.add(listenerGuid);
      sub.onTick = onTick; // Keep latest
    }
  }

  unsubscribeBars(listenerGuid: string): void {
    const seriesId = this._guidToSeriesId.get(listenerGuid);
    if (!seriesId) return;

    this._guidToSeriesId.delete(listenerGuid);

    const sub = this._subscriptions.get(seriesId);
    if (!sub) return;

    sub.listeners.delete(listenerGuid);

    if (sub.listeners.size === 0) {
      this._subscriptions.delete(seriesId);
      terminalWS.send({
        m: "unsubscribe_bar",
        p: [this._sessionId, seriesId],
      });
    }
  }

  async ensureSession(): Promise<void> {
    if (this._isCreated) return;
    if (this._createPromise) return this._createPromise;

    this._createPromise = (async () => {
      await this.waitForConnection();

      terminalWS.send({ m: "create_chart", p: [this._sessionId, null] });

      await new Promise<void>((resolve) => {
        let done = false;
        const timer = setTimeout(() => {
          if (done) return;
          done = true;
          this._isCreated = true; // Fallback if server doesn't ack but we want to proceed
          resolve();
        }, 1000);

        this._createResolvers.push(() => {
          if (done) return;
          done = true;
          clearTimeout(timer);
          resolve();
        });
      });
    })().finally(() => {
      this._createPromise = null;
    });

    return this._createPromise;
  }

  private async waitForConnection(timeoutMs = 15000): Promise<void> {
    if (terminalWS.isConnected) return;

    const start = Date.now();
    while (!terminalWS.isConnected) {
      if (Date.now() - start > timeoutMs) {
        throw new Error("WebSocket connection timeout");
      }
      await new Promise((resolve) => setTimeout(resolve, 100));
    }
  }

  async recoverSession(): Promise<void> {
    if (this._isRecovering) return;
    this._isRecovering = true;

    try {
      await this.ensureSession();

      // Restore subscriptions
      this._subscriptions.forEach((sub) => {
        terminalWS.send({
          m: "subscribe_bar",
          p: [
            this._sessionId,
            {
              symbol: sub.symbol,
              interval: sub.interval,
              series_id: sub.seriesId,
            },
          ],
        });
      });

      // We don't necessarily re-emit pending history requests here as the chart library
      // will usually retry if it doesn't get a response, but we could if needed.
    } finally {
      this._isRecovering = false;
    }
  }

  destroy(): void {
    terminalWS.send({ m: "destroy_chart", p: [this._sessionId] });
    this._unsubs.forEach((u) => u());
    this._resolveCallbacks.forEach((cb) => cb.reject("Session destroyed"));
    this._historyCallbacks.forEach((cb) => cb.reject("Session destroyed"));
    this._subscriptions.clear();
    this._guidToSeriesId.clear();
  }
}
