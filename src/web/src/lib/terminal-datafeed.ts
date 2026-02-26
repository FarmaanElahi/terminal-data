/**
 * Custom TradingView Datafeed backed by our /api/v1/market-feeds/candles API.
 *
 * Implements the Datafeed API expected by the TradingView charting library:
 *   - onReady        → returns configuration
 *   - searchSymbols   → no-op (we handle symbol via channel bus)
 *   - resolveSymbol   → returns symbol info
 *   - getBars         → fetches candle data from our API
 *   - subscribeBars   → polls for realtime updates
 *   - unsubscribeBars → stops polling
 */

/* eslint-disable @typescript-eslint/no-explicit-any */

import api from "@/lib/api";

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
  private _lastBar: Record<string, Bar> = {};
  private _pollingTimers: Record<string, ReturnType<typeof setInterval>> = {};

  onReady(callback: (config: DatafeedConfiguration) => void): void {
    setTimeout(() => {
      callback({
        supported_resolutions: ["1D"],
        exchanges: [
          { value: "", name: "All Exchanges", desc: "" },
          { value: "NSE", name: "NSE", desc: "National Stock Exchange" },
          { value: "BSE", name: "BSE", desc: "Bombay Stock Exchange" },
          { value: "NASDAQ", name: "NASDAQ", desc: "NASDAQ" },
          { value: "NYSE", name: "NYSE", desc: "NYSE" },
        ],
        symbols_types: [{ name: "All types", value: "" }],
      });
    }, 0);
  }

  async searchSymbols(
    userInput: string,
    exchange: string,
    _symbolType: string,
    onResult: (result: any[]) => void,
  ): Promise<void> {
    try {
      const params: Record<string, string | number | null> = {
        q: userInput,
        limit: 30,
        // Override backend default of "india" — search all markets unless filtered
        market: exchange ? exchange.toLowerCase() : null,
      };

      const response = await api.get("/symbols/q", { params });
      const symbols = response.data?.items ?? [];

      const results = symbols.map(
        (s: {
          ticker: string;
          name: string;
          type: string;
          market: string;
          logo?: string;
        }) => {
          // ticker is "EXCHANGE:NAME" e.g. "NSE:RELIANCE"
          const parts = s.ticker.split(":");
          const shortName = parts.length > 1 ? parts[1] : parts[0];
          const exchange = parts.length > 1 ? parts[0] : s.market;

          const logo_urls = s.logo
            ? [`https://s3-symbol-logo.tradingview.com/${s.logo}.svg`]
            : undefined;

          return {
            symbol: shortName,
            full_name: s.ticker,
            description: s.name,
            exchange,
            ticker: s.ticker,
            type: s.type || "stock",
            logo_urls,
          };
        },
      );

      onResult(results);
    } catch {
      onResult([]);
    }
  }

  async resolveSymbol(
    symbolName: string,
    onResolve: (symbolInfo: LibrarySymbolInfo) => void,
    onError: (reason: string) => void,
  ): Promise<void> {
    try {
      // Parse exchange:ticker format (e.g. "NSE:RELIANCE" or "NASDAQ:AAPL")
      const parts = symbolName.split(":");
      const exchange = parts.length > 1 ? parts[0] : "";
      const shortName = parts.length > 1 ? parts[1] : parts[0];

      // Try to look up the real name and logo from the symbols API
      let description = shortName;
      let logo_urls: string[] | undefined;
      try {
        const response = await api.get("/symbols/q", {
          params: { q: shortName, market: null, limit: 1 },
        });
        const items = response.data?.items ?? [];
        const match = items.find(
          (s: { ticker: string }) => s.ticker === symbolName,
        );
        if (match) {
          if (match.name) description = match.name;
          if (match.logo) {
            logo_urls = [
              `https://s3-symbol-logo.tradingview.com/${match.logo}.svg`,
            ];
          }
        }
      } catch {
        // Fall back to ticker as description
      }

      const symbolInfo: LibrarySymbolInfo = {
        name: shortName,
        full_name: symbolName,
        ticker: symbolName,
        description,
        logo_urls,
        type: "stock",
        session: "0915-1530",
        exchange,
        listed_exchange: exchange,
        timezone: "Asia/Kolkata",
        format: "price",
        pricescale: 100,
        minmov: 1,
        has_intraday: false,
        has_daily: true,
        has_weekly_and_monthly: true,
        supported_resolutions: ["1D"],
        data_status: "streaming",
      };

      onResolve(symbolInfo);
    } catch (err: any) {
      onError(err?.message || "Failed to resolve symbol");
    }
  }

  async getBars(
    symbolInfo: LibrarySymbolInfo,
    _resolution: string,
    periodParams: { from: number; to: number; firstDataRequest?: boolean },
    onResult: (bars: Bar[], meta: { noData?: boolean }) => void,
    onError: (reason: string) => void,
  ): Promise<void> {
    try {
      const symbol = symbolInfo.ticker || symbolInfo.full_name;
      const response = await api.get(`/market-feeds/candles/${symbol}`);

      // API returns { data: [[t, o, h, l, c, v], ...] } — latest first
      const rows: number[][] = response.data?.data;

      if (!rows || rows.length === 0) {
        onResult([], { noData: true });
        return;
      }

      // Convert to bars, filter by time range, and sort chronologically
      const bars: Bar[] = [];
      for (const row of rows) {
        const time = row[0] * 1000; // Convert seconds → milliseconds
        if (
          time >= periodParams.from * 1000 &&
          time <= periodParams.to * 1000
        ) {
          bars.push({
            time,
            open: row[1],
            high: row[2],
            low: row[3],
            close: row[4],
            volume: row[5],
          });
        }
      }

      // Sort chronologically (oldest first) — API returns latest first
      bars.sort((a, b) => a.time - b.time);

      if (bars.length === 0) {
        onResult([], { noData: true });
        return;
      }

      // Cache the last bar for realtime updates
      this._lastBar[symbolInfo.ticker] = bars[bars.length - 1];

      onResult(bars, { noData: false });
    } catch (err: any) {
      const msg = err?.response?.data?.detail || err.message || "Unknown error";
      console.error("[TerminalDatafeed] getBars error:", msg);
      onError(msg);
    }
  }

  subscribeBars(
    symbolInfo: LibrarySymbolInfo,
    _resolution: string,
    onTick: (bar: Bar) => void,
    listenerGuid: string,
  ): void {
    // Poll the API every 30 seconds for updated candles
    this._pollingTimers[listenerGuid] = setInterval(async () => {
      try {
        const symbol = symbolInfo.ticker || symbolInfo.full_name;
        const response = await api.get(`/market-feeds/candles/${symbol}`);
        const rows: number[][] = response.data?.data;
        if (!rows || rows.length === 0) return;

        // Latest candle is first row
        const latest = rows[0];
        const bar: Bar = {
          time: latest[0] * 1000,
          open: latest[1],
          high: latest[2],
          low: latest[3],
          close: latest[4],
          volume: latest[5],
        };

        // Only tick if the bar changed
        const last = this._lastBar[symbolInfo.ticker];
        if (
          !last ||
          last.time !== bar.time ||
          last.close !== bar.close ||
          last.volume !== bar.volume
        ) {
          this._lastBar[symbolInfo.ticker] = bar;
          onTick(bar);
        }
      } catch {
        // Silently ignore polling errors
      }
    }, 30_000);
  }

  unsubscribeBars(listenerGuid: string): void {
    if (this._pollingTimers[listenerGuid]) {
      clearInterval(this._pollingTimers[listenerGuid]);
      delete this._pollingTimers[listenerGuid];
    }
  }
}
