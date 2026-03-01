import axios from "axios";
import type {
  LoginRequest,
  RegisterRequest,
  TokenResponse,
  SymbolSearchParams,
  SearchResultResponse,
  ListCreate,
  ListUpdate,
  FormulaCreate,
  FormulaValidateRequest,
  FormulaValidateResponse,
  EditorConfig,
  ConditionSetCreate,
  ConditionSetUpdate,
  ColumnSetCreate,
  ColumnSetUpdate,
  ScanResult,
} from "@/types/api";
import type {
  User,
  List,
  Formula,
  ConditionSet,
  ColumnSet,
  Symbol,
} from "@/types/models";

// ─── Axios Instance ────────────────────────────────────────────────
const api = axios.create({
  baseURL: "/api/v1",
  headers: { "Content-Type": "application/json" },
});

// ─── Auth Interceptor ──────────────────────────────────────────────
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("terminal_token");
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// ─── Auth API ──────────────────────────────────────────────────────
export const authApi = {
  login: (data: LoginRequest) =>
    api.post<TokenResponse>(
      "/auth/login",
      new URLSearchParams({
        username: data.username,
        password: data.password,
      }),
      {
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
      },
    ),
  register: (data: RegisterRequest) => api.post<User>("/auth/register", data),
  me: () => api.get<User>("/users/me"),
};

// ─── Symbols API ───────────────────────────────────────────────────
export const symbolsApi = {
  search: (params: SymbolSearchParams) =>
    api.get<SearchResultResponse>("/symbols/q", { params }),
  metadata: () =>
    api.get<{ markets: string[]; types: string[]; indexes: string[] }>(
      "/symbols/search_metadata",
    ),
};

// ─── Lists API ─────────────────────────────────────────────────────
export const listsApi = {
  all: () => api.get<List[]>("/lists"),
  get: (id: string) => api.get<List>(`/lists/${id}`),
  create: (data: ListCreate) => api.post<List>("/lists", data),
  update: (id: string, data: ListUpdate) => api.put<List>(`/lists/${id}`, data),
  delete: (id: string) => api.delete(`/lists/${id}`),
  appendSymbols: (id: string, symbols: string[]) =>
    api.post(`/lists/${id}/append_symbols`, { symbols }),
  removeSymbols: (id: string, symbols: string[]) =>
    api.post(`/lists/${id}/bulk_remove_symbols`, { symbols }),
  scan: (id: string) => api.post<ScanResult>(`/lists/${id}/scan`),
};

// ─── Formula API ───────────────────────────────────────────────────
export const formulaApi = {
  all: () => api.get<Formula[]>("/formula/functions"),
  create: (data: FormulaCreate) =>
    api.post<Formula>("/formula/functions", data),
  delete: (id: string) => api.delete(`/formula/functions/${id}`),
  validate: (data: FormulaValidateRequest) =>
    api.post<FormulaValidateResponse>("/formula/validate", data),
  editorConfig: () => api.get<EditorConfig>("/formula/editor-config"),
};

// ─── Conditions API ────────────────────────────────────────────────
export const conditionsApi = {
  all: () => api.get<ConditionSet[]>("/conditions"),
  get: (id: string) => api.get<ConditionSet>(`/conditions/${id}`),
  create: (data: ConditionSetCreate) =>
    api.post<ConditionSet>("/conditions", data),
  update: (id: string, data: ConditionSetUpdate) =>
    api.put<ConditionSet>(`/conditions/${id}`, data),
  delete: (id: string) => api.delete(`/conditions/${id}`),
};

// ─── Columns API ───────────────────────────────────────────────────
export const columnsApi = {
  all: () => api.get<ColumnSet[]>("/columns"),
  get: (id: string) => api.get<ColumnSet>(`/columns/${id}`),
  create: (data: ColumnSetCreate) => api.post<ColumnSet>("/columns", data),
  update: (id: string, data: ColumnSetUpdate) =>
    api.put<ColumnSet>(`/columns/${id}`, data),
  delete: (id: string) => api.delete(`/columns/${id}`),
};

// ─── Market Feed API ───────────────────────────────────────────────
export const marketFeedApi = {
  candles: (symbol: string) => api.get(`/market-feeds/candles/${symbol}`),
};

// ─── Community API ─────────────────────────────────────────────────
export const communityApi = {
  globalFeed: (feed: string, limit?: number) =>
    api.get(`/community/global/${feed}`, { params: { limit } }),
  symbolFeed: (symbol: string, feed: string, limit?: number) =>
    api.get(`/community/${symbol}/${feed}`, { params: { limit } }),
};

// ─── Boot API ──────────────────────────────────────────────────────

export interface BootPreferences {
  layout: unknown | null;
  settings: unknown | null;
}

export interface BootResponse {
  user: User;
  lists: List[];
  column_sets: ColumnSet[];
  condition_sets: ConditionSet[];
  formulas: Formula[];
  symbols: Symbol[];
  editor_config: FormulaEditorConfig;
  preferences: BootPreferences;
}

export const bootApi = {
  boot: () => api.get<BootResponse>("/boot"),
};

// ─── Preferences API ───────────────────────────────────────────────
export const preferencesApi = {
  get: () => api.get<BootPreferences>("/preferences"),
  update: (data: Partial<BootPreferences>) =>
    api.put<BootPreferences>("/preferences", data),
};
// ─── Formulas API ──────────────────────────────────────────────────
export const formulasApi = {
  editorConfig: () => api.get<FormulaEditorConfig>("/formulas/editor-config"),
};

export interface FormulaEditorConfig {
  languageId: string;
  tokenizerRules: Record<string, unknown>;
  languageConfig: Record<string, unknown>;
  completionItems: Array<{
    label: string;
    kind: string;
    detail: string;
    documentation?: string;
    insertText: string;
    insertTextRules?: string;
  }>;
}

export default api;
