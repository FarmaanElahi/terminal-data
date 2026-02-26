import { useCallback } from "react";
import { useLayoutStore } from "@/stores/layout-store";
import type { LayoutNode, PaneNode } from "@/types/layout";

/** Find the PaneNode that contains a specific widget instance */
function findPaneByWidgetId(
  node: LayoutNode,
  widgetId: string,
): PaneNode | null {
  if (node.type === "pane") {
    if (node.tabs.some((t) => t.id === widgetId)) return node;
    return null;
  }
  for (const child of node.children) {
    const found = findPaneByWidgetId(child, widgetId);
    if (found) return found;
  }
  return null;
}

/**
 * Hook for widgets to access their settings and the channel-linked symbol.
 *
 * Symbol linking is purely store-driven — no event bus needed.
 * Widgets with a channel color read/write their color's context.
 * Widgets without a channel color fall back to the global context,
 * so symbol linking works by default even without explicit linking.
 */
export function useWidget<T = Record<string, unknown>>(instanceId: string) {
  const layout = useLayoutStore((s) => s.getActiveLayout());
  const updateWidgetSettings = useLayoutStore((s) => s.updateWidgetSettings);
  const updateChannelContext = useLayoutStore((s) => s.updateChannelContext);
  const updateGlobalContext = useLayoutStore((s) => s.updateGlobalContext);

  // Find this widget's pane and tab
  const pane = findPaneByWidgetId(layout.root, instanceId);
  const tab = pane?.tabs.find((t) => t.id === instanceId);
  const channelColor = tab?.channelColor ?? null;
  const settings = (tab?.settings ?? {}) as T;

  // Read the appropriate context: channel-specific or global fallback
  const channelContexts = useLayoutStore((s) => s.channelContexts);
  const globalContext = useLayoutStore((s) => s.globalContext);
  const channelContext = channelColor
    ? channelContexts[channelColor]
    : globalContext;

  const updateSettings = useCallback(
    (patch: Partial<T>) => {
      updateWidgetSettings(instanceId, patch as Record<string, unknown>);
    },
    [instanceId, updateWidgetSettings],
  );

  /** Set the active symbol for this widget's linked channel (or global) */
  const setChannelSymbol = useCallback(
    (symbol: string) => {
      if (channelColor) {
        updateChannelContext(channelColor, { symbol });
      } else {
        updateGlobalContext({ symbol });
      }
    },
    [channelColor, updateChannelContext, updateGlobalContext],
  );

  return {
    instanceId,
    settings,
    updateSettings,
    channelColor,
    channelContext,
    setChannelSymbol,
  };
}
