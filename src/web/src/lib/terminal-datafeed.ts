import type { ChartSession } from "./chart-session";
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

// ─── Datafeed Implementation ───────────────────────────────────────

export class TerminalDatafeed {
  private _session: ChartSession;
  private _lastBarTimes: Map<string, number> = new Map(); // series_id -> last timestamp

  constructor(session: ChartSession) {
    this._session = session;
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
      const matchesMarket = !market || (s.exchange ?? "").toLowerCase() === market;
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
    // Fast path: resolve from boot data — zero network round-trip.
    // All symbols loaded at startup can be resolved instantly.
    const local = this._resolveLocally(symbolName);
    if (local) {
      onResolve(local);
      return;
    }

    // Slow path: unknown symbol — ask the backend via WebSocket.
    try {
      const info = await this._session.resolveSymbol(symbolName);
      onResolve(info);
    } catch (err) {
      onError(String(err));
    }
  }

  private _resolveLocally(symbolName: string): LibrarySymbolInfo | null {
    const symbols = useAuthStore.getState().symbols;
    const s = symbols.find((sym) => sym.ticker === symbolName);
    if (!s) return null;

    const exchange = symbolName.includes(":")
      ? symbolName.split(":")[0]
      : (s.exchange || "");

    return {
      name: s.name,
      full_name: s.ticker,
      ticker: s.ticker,
      description: s.name,
      type: s.type || "stock",
      // Defaults mirror the backend SymbolResolvedData model exactly.
      // If per-symbol session/timezone ever diverge, add those fields to boot data.
      session: "0915-1530",
      exchange,
      listed_exchange: exchange,
      timezone: "Asia/Kolkata",
      format: "price",
      pricescale: 100,
      minmov: 1,
      has_intraday: true,
      has_daily: true,
      has_weekly_and_monthly: true,
      // Use the full datafeed resolution list so every toolbar option is enabled.
      supported_resolutions: [
        "1", "2", "3", "5", "10", "15", "20", "30", "45",
        "60", "120", "180", "240", "1D", "1W", "1M", "3M", "6M", "12M",
      ],
      data_status: "streaming",
      logo_urls: s.logo
        ? [`https://s3-symbol-logo.tradingview.com/${s.logo}.svg`]
        : undefined,
    };
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
      `[Datafeed ${this._session.sessionId}] getBars for ${symbol} @ ${resolution}. requestId=${requestId}`,
    );

    try {
      const { candles, noData } = await this._session.getBars(
        symbol,
        interval,
        fromDate,
        toDate,
        requestId,
      );

      // c = [time_ms, open, high, close, low, volume]
      const bars: Bar[] = candles.map((c) => ({
        time: c[0],
        open: c[1],
        high: c[2],
        close: c[3],
        low: c[4],
        volume: c[5],
      }));

      bars.sort((a, b) => a.time - b.time);

      // Update last bar time for real-time order checks
      if (bars.length > 0) {
        this._lastBarTimes.set(requestId, bars[bars.length - 1].time);
      }

      onResult(bars, { noData });
    } catch (err) {
      onError(String(err));
    }
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

    // Wrap onTick to include out-of-order protection
    const wrappedOnTick = (bar: Bar) => {
      const lastTime = this._lastBarTimes.get(seriesId) || 0;
      if (bar.time < lastTime) {
        console.warn(
          `[Datafeed ${this._session.sessionId}] Out-of-order tick for ${seriesId}. Dropping.`,
        );
        return;
      }
      this._lastBarTimes.set(seriesId, bar.time);
      onTick(bar);
    };

    this._session.subscribeBars(symbol, interval, wrappedOnTick, listenerGuid);
  }

  unsubscribeBars(listenerGuid: string): void {
    this._session.unsubscribeBars(listenerGuid);
  }

  private _mapResolution(resolution: string): string {
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
      "1D": "1d",
      D: "1d",
      "1W": "1w",
      "1M": "1M",
      "3M": "3mo",
      "6M": "6mo",
      "12M": "1y",
    };
    return map[resolution] || "1d";
  }
}
