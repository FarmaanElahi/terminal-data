import { create } from "zustand";
import type { ScreenerFilterRow, ScreenerValues } from "@/types/ws";

interface ScreenerState {
  sessionId: string | null;
  tickers: ScreenerFilterRow[];
  values: ScreenerValues;
  isLoading: boolean;
  lastUpdate: number | null;

  setSession: (id: string) => void;
  setTickers: (tickers: ScreenerFilterRow[]) => void;
  setValues: (values: ScreenerValues) => void;
  updateValue: (ticker: string, updates: Record<string, unknown>) => void;
  reset: () => void;
}

export const useScreenerStore = create<ScreenerState>((set, get) => ({
  sessionId: null,
  tickers: [],
  values: {},
  isLoading: true,
  lastUpdate: null,

  setSession: (id) => set({ sessionId: id, isLoading: true }),

  setTickers: (tickers) =>
    set({ tickers, isLoading: false, lastUpdate: Date.now() }),

  setValues: (values) => set({ values, lastUpdate: Date.now() }),

  updateValue: (ticker, updates) => {
    const { tickers, values } = get();
    const tickerIndex = tickers.findIndex((t) => t.ticker === ticker);
    if (tickerIndex === -1) return;

    const newValues = { ...values };
    for (const [col, val] of Object.entries(updates)) {
      if (newValues[col]) {
        const arr = [...newValues[col]];
        arr[tickerIndex] = val;
        newValues[col] = arr;
      }
    }
    set({ values: newValues, lastUpdate: Date.now() });
  },

  reset: () =>
    set({
      sessionId: null,
      tickers: [],
      values: {},
      isLoading: true,
      lastUpdate: null,
    }),
}));
