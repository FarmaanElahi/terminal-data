import { create } from "zustand";
import type {
  User,
  List,
  ColumnSet,
  ConditionSet,
  Formula,
} from "@/types/models";
import { authApi, bootApi, setAuthToken } from "@/lib/api";
import { terminalWS } from "@/lib/ws";

interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  isBooted: boolean;

  // Boot data — pre-loaded on login for instant UI
  lists: List[];
  columnSets: ColumnSet[];
  conditionSets: ConditionSet[];
  formulas: Formula[];

  login: (username: string, password: string) => Promise<void>;
  register: (username: string, password: string) => Promise<void>;
  logout: () => void;
  loadBoot: () => Promise<void>;
  setToken: (token: string) => void;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  token: localStorage.getItem("terminal_token"),
  isAuthenticated: !!localStorage.getItem("terminal_token"),
  isLoading: false,
  isBooted: false,

  lists: [],
  columnSets: [],
  conditionSets: [],
  formulas: [],

  login: async (username: string, password: string) => {
    set({ isLoading: true });
    try {
      const { data } = await authApi.login({ username, password });
      const token = data.access_token;
      localStorage.setItem("terminal_token", token);
      setAuthToken(token);
      terminalWS.connect(token);

      // Boot: fetch all user data in one request
      const { data: boot } = await bootApi.boot();
      set({
        token,
        user: boot.user,
        lists: boot.lists,
        columnSets: boot.column_sets,
        conditionSets: boot.condition_sets,
        formulas: boot.formulas,
        isAuthenticated: true,
        isBooted: true,
        isLoading: false,
      });
    } catch (err) {
      set({ isLoading: false });
      throw err;
    }
  },

  register: async (username: string, password: string) => {
    set({ isLoading: true });
    try {
      await authApi.register({ username, password });
      // Auto-login after register
      await get().login(username, password);
    } catch (err) {
      set({ isLoading: false });
      throw err;
    }
  },

  logout: () => {
    localStorage.removeItem("terminal_token");
    setAuthToken(null);
    terminalWS.disconnect();
    set({
      user: null,
      token: null,
      isAuthenticated: false,
      isBooted: false,
      lists: [],
      columnSets: [],
      conditionSets: [],
      formulas: [],
    });
  },

  loadBoot: async () => {
    const token = get().token;
    if (!token) return;

    setAuthToken(token);
    try {
      const { data: boot } = await bootApi.boot();
      terminalWS.connect(token);
      set({
        user: boot.user,
        lists: boot.lists,
        columnSets: boot.column_sets,
        conditionSets: boot.condition_sets,
        formulas: boot.formulas,
        isAuthenticated: true,
        isBooted: true,
      });
    } catch {
      // Token expired or invalid
      get().logout();
    }
  },

  setToken: (token: string) => {
    localStorage.setItem("terminal_token", token);
    setAuthToken(token);
    set({ token, isAuthenticated: true });
  },
}));
