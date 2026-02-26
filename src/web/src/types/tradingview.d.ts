/**
 * Type declarations for TradingView Charting Library loaded via CDN.
 *
 * The library exposes globals `TradingView` and `TradingViewDatafeed`
 * via <script> tags in index.html.
 */

/* eslint-disable @typescript-eslint/no-explicit-any */

// ─── Widget Options ────────────────────────────────────────────────

interface ChartingLibraryWidgetOptions {
  symbol?: string;
  interval?: string;
  container: string | HTMLElement;
  datafeed: any;
  library_path?: string;
  locale?: string;
  fullscreen?: boolean;
  autosize?: boolean;
  theme?: "light" | "dark";
  disabled_features?: string[];
  enabled_features?: string[];
  overrides?: Record<string, any>;
  charts_storage_url?: string;
  charts_storage_api_version?: string;
  client_id?: string;
  user_id?: string;
  custom_css_url?: string;
  width?: number | string;
  height?: number | string;
  timezone?: string;
  debug?: boolean;
  favorites?: { intervals?: string[]; chartTypes?: string[] };
  loading_screen?: { backgroundColor?: string; foregroundColor?: string };
  toolbar_bg?: string;
  [key: string]: any;
}

// ─── Active Chart ──────────────────────────────────────────────────

interface IChartWidgetApi {
  symbol(): string;
  setSymbol(symbol: string, callback?: () => void): void;
  resolution(): string;
  setResolution(resolution: string, callback?: () => void): void;
  onSymbolChanged(): ISubscription;
  onIntervalChanged(): ISubscription;
  [key: string]: any;
}

interface ISubscription {
  subscribe(
    obj: null | object,
    callback: (...args: any[]) => void,
    ...args: any[]
  ): void;
  unsubscribe(obj: null | object, callback: (...args: any[]) => void): void;
  unsubscribeAll(obj: null | object): void;
}

// ─── Widget Instance ───────────────────────────────────────────────

interface IChartingLibraryWidget {
  onChartReady(callback: () => void): void;
  headerReady(): Promise<void>;
  activeChart(): IChartWidgetApi;
  setSymbol(symbol: string, interval: string, callback?: () => void): void;
  remove(): void;
  resize(): void;
  changeTheme(
    theme: "light" | "dark",
    options?: { disableUndo?: boolean },
  ): void;
  createButton(options?: {
    useTradingViewStyle?: boolean;
    align?: "left" | "right";
  }): HTMLElement;
  customSymbolStatus(): any;
  [key: string]: any;
}

// ─── Globals ───────────────────────────────────────────────────────

declare namespace TradingView {
  class widget implements IChartingLibraryWidget {
    constructor(options: ChartingLibraryWidgetOptions);
    onChartReady(callback: () => void): void;
    headerReady(): Promise<void>;
    activeChart(): IChartWidgetApi;
    setSymbol(symbol: string, interval: string, callback?: () => void): void;
    remove(): void;
    resize(): void;
    changeTheme(
      theme: "light" | "dark",
      options?: { disableUndo?: boolean },
    ): void;
    createButton(options?: {
      useTradingViewStyle?: boolean;
      align?: "left" | "right";
    }): HTMLElement;
    customSymbolStatus(): any;
    [key: string]: any;
  }
}

declare namespace TradingViewDatafeed {
  class TradingViewDatafeed {
    constructor(...args: any[]);
    [key: string]: any;
  }
}
