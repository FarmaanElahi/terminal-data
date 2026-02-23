import {
  createContext,
  useContext,
  useRef,
  useCallback,
  useEffect,
  useState,
  memo,
} from "react";
import { createPortal } from "react-dom";
import { getWidget } from "@/lib/widget-registry";
import { useLayoutStore } from "@/stores/layout-store";
import type { LayoutNode } from "@/types/layout";

// ─── Portal Target Registry ────────────────────────────────────────

interface PortalRegistry {
  register(instanceId: string, el: HTMLElement): void;
  unregister(instanceId: string): void;
}

const PortalCtx = createContext<PortalRegistry>({
  register: () => {},
  unregister: () => {},
});

/**
 * Hook for PaneContainer to register its body div as a portal target.
 * The widget will be portaled into this element.
 */
export function usePortalTarget(instanceId: string) {
  const { register, unregister } = useContext(PortalCtx);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (el) register(instanceId, el);
    return () => unregister(instanceId);
  }, [instanceId, register, unregister]);

  return ref;
}

// ─── Collect all active widget instances ────────────────────────────

interface ActiveWidget {
  instanceId: string;
  widgetType: string;
  settings: Record<string, unknown>;
}

function collectFromTree(node: LayoutNode, result: ActiveWidget[]): void {
  if (node.type === "pane") {
    const tab = node.tabs[node.activeTabIndex] ?? node.tabs[0];
    if (tab) {
      result.push({
        instanceId: tab.id,
        widgetType: tab.widgetType,
        settings: tab.settings,
      });
    }
    return;
  }
  for (const child of node.children) {
    collectFromTree(child, result);
  }
}

// ─── Stable widget renderer (memoized by instanceId) ───────────────

const StableWidget = memo(
  function StableWidget({
    instanceId,
    widgetType,
    settings,
  }: {
    instanceId: string;
    widgetType: string;
    settings: Record<string, unknown>;
  }) {
    const def = getWidget(widgetType);
    const Component = def?.component;

    const handleSettingsChange = useCallback(
      (patch: Record<string, unknown>) => {
        useLayoutStore.getState().updateWidgetSettings(instanceId, patch);
      },
      [instanceId],
    );

    if (!Component) return null;

    return (
      <Component
        instanceId={instanceId}
        settings={settings}
        onSettingsChange={handleSettingsChange}
      />
    );
  },
  // Custom comparison: only re-render if instanceId or widgetType change,
  // or if settings values actually changed (shallow compare)
  (prev, next) => {
    if (prev.instanceId !== next.instanceId) return false;
    if (prev.widgetType !== next.widgetType) return false;
    if (prev.settings === next.settings) return true;
    // Shallow compare settings
    const prevKeys = Object.keys(prev.settings);
    const nextKeys = Object.keys(next.settings);
    if (prevKeys.length !== nextKeys.length) return false;
    return prevKeys.every((k) => prev.settings[k] === next.settings[k]);
  },
);

// ─── Provider ──────────────────────────────────────────────────────

/**
 * WidgetPortalProvider renders all widget instances at a STABLE position
 * in the React tree. They are then portaled into their PaneContainer's
 * target div. This means widgets persist even when panes move between
 * tree ↔ floating, or when unrelated layout changes happen.
 */
export function WidgetPortalProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const targetsRef = useRef(new Map<string, HTMLElement>());
  const [, bump] = useState(0);

  const register = useCallback((id: string, el: HTMLElement) => {
    targetsRef.current.set(id, el);
    bump((n) => n + 1);
  }, []);

  const unregister = useCallback((id: string) => {
    targetsRef.current.delete(id);
    // Don't bump here — the widget stays mounted in hidden div
  }, []);

  // Collect all live widget instances
  const activeLayoutId = useLayoutStore((s) => s.activeLayoutId);
  const layouts = useLayoutStore((s) => s.layouts);
  const layout = layouts.find((l) => l.id === activeLayoutId) ?? layouts[0];

  const instances: ActiveWidget[] = [];
  if (layout) {
    collectFromTree(layout.root, instances);
    for (const fw of layout.floatingWindows) {
      const tab = fw.pane.tabs[fw.pane.activeTabIndex] ?? fw.pane.tabs[0];
      if (tab) {
        instances.push({
          instanceId: tab.id,
          widgetType: tab.widgetType,
          settings: tab.settings,
        });
      }
    }
  }

  return (
    <PortalCtx.Provider value={{ register, unregister }}>
      {children}

      {/* Render all widgets stably — they never unmount due to layout changes */}
      {instances.map(({ instanceId, widgetType, settings }) => {
        const target = targetsRef.current.get(instanceId);
        const widget = (
          <StableWidget
            key={instanceId}
            instanceId={instanceId}
            widgetType={widgetType}
            settings={settings}
          />
        );

        if (target) {
          return createPortal(widget, target, instanceId);
        }

        // Keep mounted but hidden when target not yet available
        // (e.g. during tree ↔ floating transition)
        return (
          <div key={instanceId} style={{ display: "none" }}>
            {widget}
          </div>
        );
      })}
    </PortalCtx.Provider>
  );
}
