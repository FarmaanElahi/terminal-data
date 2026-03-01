import { create } from "zustand";
import type { User, Symbol } from "@/types/models";
import { authApi, bootApi, type FormulaEditorConfig } from "@/lib/api";
import { terminalWS } from "@/lib/ws";
import type { QueryClient } from "@tanstack/react-query";
import { QUERY_KEYS } from "@/queries/query-keys";
import { useLayoutStore } from "@/stores/layout-store";
import type { WorkspaceState } from "@/types/layout";

interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  isBooted: boolean;

  // Static boot data (read-only, never mutated after boot)
  symbols: Symbol[];
  editorConfig: FormulaEditorConfig | null;

  login: (
    username: string,
    password: string,
    queryClient: QueryClient,
  ) => Promise<void>;
  register: (
    username: string,
    password: string,
    queryClient: QueryClient,
  ) => Promise<void>;
  logout: (queryClient: QueryClient) => void;
  loadBoot: (queryClient: QueryClient) => Promise<void>;
  setToken: (token: string) => void;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  token: localStorage.getItem("terminal_token"),
  isAuthenticated: !!localStorage.getItem("terminal_token"),
  isLoading: false,
  isBooted: false,
  symbols: [],
  editorConfig: null,

  login: async (username, password, queryClient) => {
    set({ isLoading: true });
    try {
      const { data } = await authApi.login({ username, password });
      const token = data.access_token;
      localStorage.setItem("terminal_token", token);
      terminalWS.connect(token);

      const { data: boot } = await bootApi.boot();

      // Hydrate TanStack Query caches
      queryClient.setQueryData(QUERY_KEYS.lists, boot.lists);
      queryClient.setQueryData(QUERY_KEYS.columnSets, boot.column_sets);
      queryClient.setQueryData(QUERY_KEYS.conditionSets, boot.condition_sets);
      queryClient.setQueryData(QUERY_KEYS.formulas, boot.formulas);

      // Initialize layout from server if available
      if (boot.preferences?.layout) {
        useLayoutStore
          .getState()
          .initializeLayout(boot.preferences.layout as WorkspaceState);
      }

      set({
        token,
        user: boot.user,
        symbols: boot.symbols,
        editorConfig: boot.editor_config,
        isAuthenticated: true,
        isBooted: true,
        isLoading: false,
      });
    } catch (err) {
      set({ isLoading: false });
      throw err;
    }
  },

  register: async (username, password, queryClient) => {
    set({ isLoading: true });
    try {
      await authApi.register({ username, password });
      await get().login(username, password, queryClient);
    } catch (err) {
      set({ isLoading: false });
      throw err;
    }
  },

  logout: (queryClient) => {
    localStorage.removeItem("terminal_token");
    terminalWS.disconnect();
    queryClient.clear();
    set({
      user: null,
      token: null,
      isAuthenticated: false,
      isBooted: false,
      symbols: [],
      editorConfig: null,
    });
  },

  loadBoot: async (queryClient) => {
    const token = get().token;
    if (!token) return;

    try {
      const { data: boot } = await bootApi.boot();
      terminalWS.connect(token);

      // Hydrate TanStack Query caches
      queryClient.setQueryData(QUERY_KEYS.lists, boot.lists);
      queryClient.setQueryData(QUERY_KEYS.columnSets, boot.column_sets);
      queryClient.setQueryData(QUERY_KEYS.conditionSets, boot.condition_sets);
      queryClient.setQueryData(QUERY_KEYS.formulas, boot.formulas);

      // Initialize layout from server if available
      if (boot.preferences?.layout) {
        useLayoutStore
          .getState()
          .initializeLayout(boot.preferences.layout as WorkspaceState);
      }

      set({
        user: boot.user,
        symbols: boot.symbols,
        editorConfig: boot.editor_config,
        isAuthenticated: true,
        isBooted: true,
      });
    } catch {
      get().logout(queryClient);
    }
  },

  setToken: (token) => {
    localStorage.setItem("terminal_token", token);
    set({ token, isAuthenticated: true });
  },
}));
