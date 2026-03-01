/**
 * ChartStorageAdapter — local-first TradingView save_load_adapter
 *
 * TradingView calls all methods directly on the adapter instance.
 * All read/write operations hit localStorage synchronously so the TV widget
 * is never blocked. Server sync runs as fire-and-forget in the background.
 *
 * Key design: `id` in LocalChart is STABLE (TV always uses this as the chart
 * identity). `serverId` tracks the server-assigned ID separately so that
 * background server sync never breaks TV's reference to the chart.
 *
 * localStorage keys:
 *   terminal_charts_v1          → LocalChart[]
 *   terminal_study_templates_v1 → Record<name, content>
 */

import { chartsApi } from "@/lib/api";

const CHARTS_KEY = "terminal_charts_v1";
const TEMPLATES_KEY = "terminal_study_templates_v1";

// ─── Local storage types ───────────────────────────────────────────

interface LocalChart {
  id: string;         // stable local ID — TV always uses this; never mutated
  serverId?: string;  // server-assigned ID (used for API calls only)
  name: string;
  symbol: string | null;
  resolution: string | null;
  content: object;
  timestamp: number;
}

// ─── Local storage helpers ─────────────────────────────────────────

function readLocalCharts(): LocalChart[] {
  try {
    return JSON.parse(localStorage.getItem(CHARTS_KEY) ?? "[]");
  } catch {
    return [];
  }
}

function writeLocalCharts(charts: LocalChart[]): void {
  localStorage.setItem(CHARTS_KEY, JSON.stringify(charts));
}

function readLocalTemplates(): Record<string, object> {
  try {
    return JSON.parse(localStorage.getItem(TEMPLATES_KEY) ?? "{}");
  } catch {
    return {};
  }
}

function writeLocalTemplates(templates: Record<string, object>): void {
  localStorage.setItem(TEMPLATES_KEY, JSON.stringify(templates));
}

function newLocalId(): string {
  return `local_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
}

function parseContent(raw: string | object): object {
  if (typeof raw === "string") {
    try {
      return JSON.parse(raw);
    } catch {
      return raw as unknown as object;
    }
  }
  return raw;
}

// ─── Adapter ──────────────────────────────────────────────────────

export class ChartStorageAdapter {
  /**
   * Load charts and study templates from server into localStorage.
   * Called concurrently with TV widget init — does not block chart load.
   * Matches server charts by serverId to avoid duplicates.
   */
  async hydrate(): Promise<void> {
    try {
      const [chartsRes, templatesRes] = await Promise.all([
        chartsApi.list(),
        chartsApi.listStudyTemplates(),
      ]);

      const local = readLocalCharts();
      // Match by serverId (already hydrated) or by server id stored as localId (legacy)
      const knownServerIds = new Set(
        local.flatMap((c) => [c.serverId, c.id].filter(Boolean) as string[]),
      );

      const newCharts = await Promise.all(
        chartsRes.data
          .filter((sc) => !knownServerIds.has(sc.id))
          .map((sc) =>
            chartsApi.getContent(sc.id).then((r) => ({
              id: newLocalId(),
              serverId: sc.id,
              name: sc.name,
              symbol: sc.symbol,
              resolution: sc.resolution,
              content: r.data.content,
              timestamp: Date.now(),
            })),
          ),
      );

      if (newCharts.length > 0) {
        writeLocalCharts([...local, ...newCharts]);
      }

      // Hydrate study templates
      const localTemplates = readLocalTemplates();
      let changed = false;

      for (const tmpl of templatesRes.data) {
        if (!(tmpl.name in localTemplates)) {
          try {
            const res = await chartsApi.getStudyTemplateContent(tmpl.name);
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            const content = (res.data as any).content;
            if (content) {
              localTemplates[tmpl.name] =
                typeof content === "string" ? JSON.parse(content) : content;
              changed = true;
            }
          } catch {
            /* skip failed template */
          }
        }
      }

      if (changed) {
        writeLocalTemplates(localTemplates);
      }
    } catch {
      /* hydration failure is non-fatal */
    }
  }

  // ─── TradingView save_load_adapter interface ──────────────────────

  async getAllCharts(): Promise<
    Array<{
      id: string;
      name: string;
      symbol: string;
      resolution: string;
      timestamp: number;
    }>
  > {
    return readLocalCharts().map((c) => ({
      id: c.id,
      name: c.name,
      symbol: c.symbol ?? "",
      resolution: c.resolution ?? "",
      timestamp: c.timestamp,
    }));
  }

  async saveChart(data: {
    id?: string;
    name: string;
    symbol: string;
    resolution: string;
    content: string;
  }): Promise<string> {
    const content = parseContent(data.content);
    const charts = readLocalCharts();
    const existingIdx = data.id
      ? charts.findIndex((c) => c.id === data.id)
      : -1;

    if (existingIdx >= 0) {
      // Update existing — id stays stable, only mutable fields change
      const existing = charts[existingIdx];
      charts[existingIdx] = {
        ...existing,
        name: data.name,
        symbol: data.symbol,
        resolution: data.resolution,
        content,
        timestamp: Date.now(),
      };
      writeLocalCharts(charts);

      // Server sync: PUT if we have a serverId, else POST (first server save)
      chartsApi
        .save({
          id: existing.serverId,
          name: data.name,
          symbol: data.symbol,
          resolution: data.resolution,
          content,
        })
        .then((res) => {
          if (!existing.serverId) {
            // First time this chart reaches the server — record its serverId
            const current = readLocalCharts();
            const idx = current.findIndex((c) => c.id === existing.id);
            if (idx >= 0) {
              current[idx].serverId = res.data.id;
              writeLocalCharts(current);
            }
          }
        })
        .catch(() => {});

      return existing.id;
    }

    // New chart — generate a stable local ID that TV will use going forward
    const localId = newLocalId();
    charts.push({
      id: localId,
      name: data.name,
      symbol: data.symbol,
      resolution: data.resolution,
      content,
      timestamp: Date.now(),
    });
    writeLocalCharts(charts);

    // Background server create — store serverId without touching localId
    chartsApi
      .save({
        name: data.name,
        symbol: data.symbol,
        resolution: data.resolution,
        content,
      })
      .then((res) => {
        const current = readLocalCharts();
        const idx = current.findIndex((c) => c.id === localId);
        if (idx >= 0) {
          current[idx].serverId = res.data.id;
          writeLocalCharts(current);
        }
      })
      .catch(() => {});

    return localId;
  }

  async getChartContent(id: string): Promise<string> {
    const chart = readLocalCharts().find((c) => c.id === id);
    if (chart) {
      return JSON.stringify(chart.content);
    }
    // Fallback: fetch from server using id directly (may be a serverId)
    const res = await chartsApi.getContent(id);
    return JSON.stringify(res.data.content);
  }

  async removeChart(id: string): Promise<void> {
    const chart = readLocalCharts().find((c) => c.id === id);
    writeLocalCharts(readLocalCharts().filter((c) => c.id !== id));
    // Use serverId for server deletion if available
    const serverTarget = chart?.serverId ?? id;
    if (serverTarget && !serverTarget.startsWith("local_")) {
      chartsApi.remove(serverTarget).catch(() => {});
    }
  }

  async getAllStudyTemplates(): Promise<Array<{ name: string }>> {
    return Object.keys(readLocalTemplates()).map((name) => ({ name }));
  }

  async saveStudyTemplate(data: {
    name: string;
    content: string;
  }): Promise<void> {
    const content = parseContent(data.content);
    const templates = readLocalTemplates();
    templates[data.name] = content;
    writeLocalTemplates(templates);
    chartsApi.saveStudyTemplate(data.name, content).catch(() => {});
  }

  // TV expects Promise<string> (raw content string), not Promise<{content: string}>
  async getStudyTemplateContent(template: { name: string }): Promise<string> {
    const templates = readLocalTemplates();
    if (template.name in templates) {
      return JSON.stringify(templates[template.name]);
    }
    // Fallback: fetch from server
    const res = await chartsApi.getStudyTemplateContent(template.name);
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const content = (res.data as any).content;
    return typeof content === "string" ? content : JSON.stringify(content);
  }

  async removeStudyTemplate(template: { name: string }): Promise<void> {
    const templates = readLocalTemplates();
    delete templates[template.name];
    writeLocalTemplates(templates);
    chartsApi.removeStudyTemplate(template.name).catch(() => {});
  }
}
