import { useCallback, useEffect } from "react";
import { useLayoutStore } from "@/stores/layout-store";
import { channelBus } from "@/lib/channel-bus";
import type { ChannelEvent, LayoutNode, PaneNode } from "@/types/layout";

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
 * Hook for widgets to access their settings and the channel bus.
 *
 * Usage inside a widget component:
 * ```
 * const { settings, updateSettings, broadcast, useChannelEvent } = useWidget<MySettings>();
 * ```
 */
export function useWidget<T = Record<string, unknown>>(instanceId: string) {
  const layout = useLayoutStore((s) => s.getActiveLayout());
  const updateWidgetSettings = useLayoutStore((s) => s.updateWidgetSettings);

  // Find this widget's pane to get channel color
  const pane = findPaneByWidgetId(layout.root, instanceId);
  const channelColor = pane?.channelColor ?? null;

  // Find this widget instance
  const tab = pane?.tabs.find((t) => t.id === instanceId);
  const settings = (tab?.settings ?? {}) as T;

  const updateSettings = useCallback(
    (patch: Partial<T>) => {
      updateWidgetSettings(instanceId, patch as Record<string, unknown>);
    },
    [instanceId, updateWidgetSettings],
  );

  const broadcast = useCallback(
    (type: string, payload: unknown) => {
      if (!channelColor) return;
      channelBus.broadcast({
        type,
        payload,
        sourceId: instanceId,
        channel: channelColor,
      });
    },
    [instanceId, channelColor],
  );

  const useChannelEvent = (handler: (event: ChannelEvent) => void) => {
    useEffect(() => {
      if (!channelColor) return;
      return channelBus.subscribe(channelColor, (event) => {
        // Don't receive own events
        if (event.sourceId === instanceId) return;
        handler(event);
      });
    }, [channelColor, handler]);
  };

  return {
    instanceId,
    settings,
    updateSettings,
    broadcast,
    useChannelEvent,
    channelColor,
  };
}
