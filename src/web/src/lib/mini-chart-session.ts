import { terminalWS } from "@/lib/ws";
import type { WSMessage } from "@/types/ws";
import type { MiniChartBar } from "@/types/mini-chart";

type BarListener = (bar: MiniChartBar) => void;

interface PendingHistoryRequest {
  symbol: string;
  interval: string;
  fromDate: string;
  toDate: string;
}

const DAY_MS = 24 * 60 * 60 * 1000;

function getHistoryRange(
  interval: string,
  toDateOverride?: Date,
): { fromDate: string; toDate: string } {
  void interval;
  const toDate = toDateOverride ? new Date(toDateOverride) : new Date();
  const fromDate = new Date(toDate);
  // Initial mini-chart load window is capped to 6 months for faster screening.
  fromDate.setMonth(toDate.getMonth() - 6);

  return {
    fromDate: fromDate.toISOString().slice(0, 10),
    toDate: toDate.toISOString().slice(0, 10),
  };
}

function mapTimeframeToInterval(timeframe: string): string {
  const map: Record<string, string> = {
    "1": "1m",
    "2": "2m",
    "3": "3m",
    "5": "5m",
    "10": "10m",
    "15": "15m",
    "20": "20m",
    "30": "30m",
    "45": "45m",
    "60": "1h",
    "120": "2h",
    "180": "3h",
    "240": "4h",
    D: "1d",
    "1D": "1d",
    W: "1w",
    "1W": "1w",
    M: "1M",
    "1M": "1M",
    "3M": "3M",
    "6M": "6M",
    "12M": "12M",
  };
  return map[timeframe] ?? "1d";
}

function toBar(input: {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}): MiniChartBar {
  return {
    time: input.time,
    open: input.open,
    high: input.high,
    low: input.low,
    close: input.close,
    volume: input.volume,
  };
}

function mergeBar(prev: MiniChartBar[], next: MiniChartBar): MiniChartBar[] {
  if (prev.length === 0) return [next];
  const last = prev[prev.length - 1];
  if (next.time === last.time) {
    return [...prev.slice(0, -1), next];
  }
  if (next.time > last.time) {
    return [...prev, next];
  }

  const idx = prev.findIndex((bar) => bar.time === next.time);
  if (idx === -1) return prev;

  const out = [...prev];
  out[idx] = next;
  return out;
}

function mergeHistory(existing: MiniChartBar[], incoming: MiniChartBar[]): MiniChartBar[] {
  if (existing.length === 0) return incoming;
  if (incoming.length === 0) return existing;

  const byTime = new Map<number, MiniChartBar>();
  for (const bar of existing) byTime.set(bar.time, bar);
  for (const bar of incoming) byTime.set(bar.time, bar);
  return Array.from(byTime.values()).sort((a, b) => a.time - b.time);
}

export class MiniChartSession {
  private sessionId: string;
  private isCreated = false;
  private createPromise: Promise<void> | null = null;
  private isRecovering = false;
  private createResolvers: Array<() => void> = [];

  private historyCache = new Map<string, MiniChartBar[]>();
  private historyRequestToCacheKey = new Map<string, string>();
  private historyRequests = new Map<string, PendingHistoryRequest>();
  private historyRequestGcTimers = new Map<string, ReturnType<typeof setTimeout>>();
  private historyRangesRequested = new Set<string>();
  private historyBackfillInFlight = new Set<string>();
  private readonly historyTimeoutMs = 45000;

  private historyResolvers = new Map<
    string,
    {
      resolve: (bars: MiniChartBar[]) => void;
      reject: (err: Error) => void;
      timeoutId: ReturnType<typeof setTimeout>;
    }
  >();

  private listeners = new Map<string, Set<BarListener>>();
  private unsubs: Array<() => void> = [];

  constructor() {
    this.sessionId =
      typeof crypto !== "undefined" && crypto.randomUUID
        ? crypto.randomUUID()
        : Math.random().toString(36).slice(2);

    this.unsubs.push(
      terminalWS.on("chart_session_created", (msg: WSMessage) => {
        const [sid] = (msg.p ?? []) as [string];
        if (sid !== this.sessionId) return;

        this.isCreated = true;
        const resolvers = [...this.createResolvers];
        this.createResolvers = [];
        resolvers.forEach((resolve) => resolve());
      }),
    );

    this.unsubs.push(
      terminalWS.on("chart_series", (msg: WSMessage) => {
        const [sid, , , candles, requestId] = msg.p as [
          string,
          string,
          string,
          Array<{
            time: number;
            open: number;
            high: number;
            low: number;
            close: number;
            volume: number;
          }>,
          string | null,
        ];
        if (sid !== this.sessionId || !requestId) return;

        const cacheKey = this.historyRequestToCacheKey.get(requestId);
        this.historyRequestToCacheKey.delete(requestId);
        this.historyRequests.delete(requestId);
        const gcTimer = this.historyRequestGcTimers.get(requestId);
        if (gcTimer) {
          clearTimeout(gcTimer);
          this.historyRequestGcTimers.delete(requestId);
        }

        const bars = candles.map((c) => toBar(c)).sort((a, b) => a.time - b.time);
        if (cacheKey) {
          const existing = this.historyCache.get(cacheKey) ?? [];
          this.historyCache.set(cacheKey, mergeHistory(existing, bars));
        }

        const pending = this.historyResolvers.get(requestId);
        if (!pending) return;

        clearTimeout(pending.timeoutId);
        this.historyResolvers.delete(requestId);

        pending.resolve(cacheKey ? (this.historyCache.get(cacheKey) ?? bars) : bars);
      }),
    );

    this.unsubs.push(
      terminalWS.on("chart_update", (msg: WSMessage) => {
        const [sid, symbol, candle, seriesIdFromMsg] = msg.p as [
          string,
          string,
          {
            time: number;
            open: number;
            high: number;
            low: number;
            close: number;
            volume: number;
          },
          string | null,
        ];
        if (sid !== this.sessionId) return;

        const bar = toBar(candle);

        if (seriesIdFromMsg) {
          const specific = this.listeners.get(seriesIdFromMsg);
          if (specific) {
            specific.forEach((fn) => fn(bar));

            const cached = this.historyCache.get(seriesIdFromMsg);
            if (cached) {
              this.historyCache.set(seriesIdFromMsg, mergeBar(cached, bar));
            }

            return;
          }
        }

        this.listeners.forEach((set, key) => {
          if (key.startsWith(`${symbol}|`)) {
            set.forEach((fn) => fn(bar));
          }
        });
      }),
    );

    this.unsubs.push(
      terminalWS.on("error", (msg: WSMessage) => {
        const errText = String((msg.p ?? [""])[0] ?? "");
        if (
          errText.includes("Chart session") &&
          errText.includes(this.sessionId) &&
          errText.includes("not found")
        ) {
          this.isCreated = false;
          void this.recoverSession();
        }
      }),
    );

    void this.ensureSession();
  }

  async loadHistory(symbol: string, timeframe: string): Promise<MiniChartBar[]> {
    const interval = mapTimeframeToInterval(timeframe);
    const cacheKey = `${symbol}|${interval}`;
    const cached = this.historyCache.get(cacheKey);
    if (cached && cached.length > 0) {
      return cached;
    }

    const { fromDate, toDate } = getHistoryRange(interval);
    this.historyRangesRequested.add(`${cacheKey}|${fromDate}|${toDate}`);

    return this.requestHistory(
      cacheKey,
      { symbol, interval, fromDate, toDate },
      "mini-history",
    );
  }

  async loadHistoryBefore(
    symbol: string,
    timeframe: string,
    beforeTimeMs: number,
  ): Promise<MiniChartBar[]> {
    const interval = mapTimeframeToInterval(timeframe);
    const cacheKey = `${symbol}|${interval}`;
    if (this.historyBackfillInFlight.has(cacheKey)) {
      return this.historyCache.get(cacheKey) ?? [];
    }

    const toDate = new Date(beforeTimeMs - DAY_MS);
    const { fromDate, toDate: toDateStr } = getHistoryRange(interval, toDate);
    const rangeKey = `${cacheKey}|${fromDate}|${toDateStr}`;
    if (this.historyRangesRequested.has(rangeKey)) {
      return this.historyCache.get(cacheKey) ?? [];
    }

    this.historyRangesRequested.add(rangeKey);
    this.historyBackfillInFlight.add(cacheKey);
    let succeeded = false;

    try {
      const bars = await this.requestHistory(
        cacheKey,
        { symbol, interval, fromDate, toDate: toDateStr },
        "mini-history",
      );
      succeeded = true;
      return bars;
    } finally {
      if (!succeeded) {
        this.historyRangesRequested.delete(rangeKey);
      }
      this.historyBackfillInFlight.delete(cacheKey);
    }
  }

  private async requestHistory(
    cacheKey: string,
    payload: PendingHistoryRequest,
    requestPrefix: string,
  ): Promise<MiniChartBar[]> {
    await this.ensureSession();
    const requestId = `${requestPrefix}-${Math.random().toString(36).slice(2, 10)}`;

    return new Promise<MiniChartBar[]>((resolve, reject) => {
      const timeoutId = setTimeout(() => {
        const pending = this.historyResolvers.get(requestId);
        if (!pending) return;
        this.historyResolvers.delete(requestId);

        // Keep request metadata for a short period so late chart_series responses
        // can still populate cache and prevent repeated misses on next attempts.
        const gc = setTimeout(() => {
          this.historyRequestToCacheKey.delete(requestId);
          this.historyRequests.delete(requestId);
          this.historyRequestGcTimers.delete(requestId);
        }, 120000);
        this.historyRequestGcTimers.set(requestId, gc);

        reject(new Error("Mini chart history timeout"));
      }, this.historyTimeoutMs);

      this.historyResolvers.set(requestId, { resolve, reject, timeoutId });
      this.historyRequestToCacheKey.set(requestId, cacheKey);
      this.historyRequests.set(requestId, payload);

      terminalWS.send({
        m: "get_bar",
        p: [
          this.sessionId,
          {
            symbol: payload.symbol,
            interval: payload.interval,
            from_date: payload.fromDate,
            to_date: payload.toDate,
            series_id: requestId,
          },
        ],
      });
    });
  }

  subscribe(
    symbol: string,
    timeframe: string,
    listener: BarListener,
  ): () => void {
    const interval = mapTimeframeToInterval(timeframe);
    const key = `${symbol}|${interval}`;

    let set = this.listeners.get(key);
    const wasEmpty = !set;
    if (!set) {
      set = new Set<BarListener>();
      this.listeners.set(key, set);
    }
    set.add(listener);

    if (wasEmpty) {
      void this.ensureSession()
        .then(() => {
          if (!this.listeners.has(key)) return;
          terminalWS.send({
            m: "subscribe_bar",
            p: [
              this.sessionId,
              {
                symbol,
                interval,
                series_id: key,
              },
            ],
          });
        })
        .catch(() => {
          // No-op: session recovery path handles retries
        });
    }

    return () => {
      const current = this.listeners.get(key);
      if (!current) return;
      current.delete(listener);
      if (current.size === 0) {
        this.listeners.delete(key);
        terminalWS.send({
          m: "unsubscribe_bar",
          p: [this.sessionId, key],
        });
      }
    };
  }

  destroy(): void {
    this.historyResolvers.forEach(({ reject, timeoutId }) => {
      clearTimeout(timeoutId);
      reject(new Error("Mini chart session destroyed"));
    });

    this.historyResolvers.clear();
    this.historyRequestToCacheKey.clear();
    this.historyRequests.clear();
    this.historyRequestGcTimers.forEach((timerId) => clearTimeout(timerId));
    this.historyRequestGcTimers.clear();
    this.historyRangesRequested.clear();
    this.historyBackfillInFlight.clear();
    this.historyCache.clear();

    this.listeners.forEach((_set, key) => {
      terminalWS.send({ m: "unsubscribe_bar", p: [this.sessionId, key] });
    });
    this.listeners.clear();

    terminalWS.send({ m: "destroy_chart", p: [this.sessionId] });

    this.unsubs.forEach((u) => u());
    this.unsubs = [];
  }

  private async ensureSession(): Promise<void> {
    if (this.isCreated) return;
    if (this.createPromise) return this.createPromise;

    this.createPromise = (async () => {
      await this.waitForConnection();

      terminalWS.send({ m: "create_chart", p: [this.sessionId, null] });

      await new Promise<void>((resolve) => {
        let done = false;
        const timer = setTimeout(() => {
          if (done) return;
          done = true;
          this.isCreated = true;
          resolve();
        }, 1000);

        this.createResolvers.push(() => {
          if (done) return;
          done = true;
          clearTimeout(timer);
          resolve();
        });
      });
    })().finally(() => {
      this.createPromise = null;
    });

    return this.createPromise;
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

  private async recoverSession(): Promise<void> {
    if (this.isRecovering) return;

    this.isRecovering = true;
    try {
      await this.ensureSession();

      this.listeners.forEach((_set, key) => {
        const [symbol, interval] = key.split("|");
        terminalWS.send({
          m: "subscribe_bar",
          p: [
            this.sessionId,
            {
              symbol,
              interval,
              series_id: key,
            },
          ],
        });
      });

      this.historyRequests.forEach((payload, requestId) => {
        if (!this.historyResolvers.has(requestId)) return;
        terminalWS.send({
          m: "get_bar",
          p: [
            this.sessionId,
            {
              symbol: payload.symbol,
              interval: payload.interval,
              from_date: payload.fromDate,
              to_date: payload.toDate,
              series_id: requestId,
            },
          ],
        });
      });
    } finally {
      this.isRecovering = false;
    }
  }
}
