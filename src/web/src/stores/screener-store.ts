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
  reset: () => void;
}

export const useScreenerStore = create<ScreenerState>((set) => ({
  sessionId: null,
  tickers: [],
  values: {},
  isLoading: true,
  lastUpdate: null,

  setSession: (id) => set({ sessionId: id, isLoading: true }),

  setTickers: (tickers) =>
    set({ tickers, isLoading: false, lastUpdate: Date.now() }),

  setValues: (values) => set({ values, lastUpdate: Date.now() }),

  reset: () =>
    set({
      sessionId: null,
      tickers: [],
      values: {},
      isLoading: true,
      lastUpdate: null,
    }),
}));
