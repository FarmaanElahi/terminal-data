import { create } from "zustand";
import { persist } from "zustand/middleware";
import type {
  LayoutNode,
  SplitNode,
  PaneNode,
  WidgetInstance,
  FloatingWindow,
  LayoutTab,
  WorkspaceState,
  DropZone,
  ChannelColor,
  ChannelContext,
  Theme,
} from "@/types/layout";
import { getWidget } from "@/lib/widget-registry";

// ─── Helpers ───────────────────────────────────────────────────────

function uid(): string {
  return crypto.randomUUID().slice(0, 8);
}

function createPane(
  widgetType: string,
  settings?: Record<string, unknown>,
): PaneNode {
  const def = getWidget(widgetType);
  return {
    type: "pane",
    id: uid(),
    tabs: [
      {
        id: uid(),
        widgetType,
        title: def?.title ?? widgetType,
        settings: settings ?? def?.defaultSettings ?? {},
        channelColor: null,
      },
    ],
    activeTabIndex: 0,
  };
}

function createDefaultLayout(): LayoutTab {
  return {
    id: uid(),
    name: "Layout 1",
    root: createPane("screener"),
    floatingWindows: [],
  };
}

// ─── Tree traversal helpers ────────────────────────────────────────

function findNode(root: LayoutNode, id: string): LayoutNode | null {
  if (root.id === id) return root;
  if (root.type === "split") {
    for (const child of root.children) {
      const found = findNode(child, id);
      if (found) return found;
    }
  }
  return null;
}

function recursiveGenerateIds(node: LayoutNode): LayoutNode {
  const newNode = { ...node, id: uid() };
  if (newNode.type === "split") {
    newNode.children = newNode.children.map(recursiveGenerateIds);
  } else if (newNode.type === "pane") {
    newNode.tabs = newNode.tabs.map((tab) => ({
      ...tab,
      id: uid(),
    }));
  }
  return newNode;
}

/**
 * Remove a node from the tree. If its parent split has only one child
 * left, collapse the parent by replacing itself with that child.
 */
function removeNode(root: LayoutNode, targetId: string): LayoutNode | null {
  if (root.id === targetId) return null; // removed the root

  if (root.type === "split") {
    const newChildren: LayoutNode[] = [];
    const newSizes: number[] = [];
    let removedSize = 0;

    for (let i = 0; i < root.children.length; i++) {
      if (root.children[i].id === targetId) {
        removedSize = root.sizes[i];
      } else {
        const updated = removeNode(root.children[i], targetId);
        if (updated) {
          newChildren.push(updated);
          newSizes.push(root.sizes[i]);
        } else {
          removedSize += root.sizes[i];
        }
      }
    }

    if (newChildren.length === 0) return null;
    if (newChildren.length === 1) return newChildren[0]; // collapse

    // Re-normalize sizes
    const total = newSizes.reduce((a, b) => a + b, 0);
    const normalized = newSizes.map(
      (s) => (s + removedSize / newSizes.length) / (total + removedSize),
    );
    // Simpler: just re-normalize
    const sum = normalized.reduce((a, b) => a + b, 0);

    return {
      ...root,
      children: newChildren,
      sizes: normalized.map((s) => s / sum),
    };
  }

  return root;
}

// ─── Store ─────────────────────────────────────────────────────────

interface LayoutActions {
  // Tree mutations
  splitPane: (
    paneId: string,
    direction: "horizontal" | "vertical",
    widgetType?: string,
  ) => void;
  addTab: (paneId: string, widgetType: string) => void;
  removeTab: (paneId: string, tabId: string) => void;
  setActiveTab: (paneId: string, index: number) => void;
  moveTab: (
    fromPaneId: string,
    tabId: string,
    toPaneId: string,
    zone: DropZone,
  ) => void;
  resizeSplit: (splitId: string, sizes: number[]) => void;
  removePane: (paneId: string) => void;
  updateWidgetSettings: (
    widgetId: string,
    patch: Record<string, unknown>,
  ) => void;

  // Channel
  setTabChannel: (tabId: string, color: ChannelColor | null) => void;

  // Floating
  floatPane: (paneId: string) => void;
  dockPane: (floatingId: string, targetPaneId: string, zone: DropZone) => void;
  updateFloatingPosition: (id: string, x: number, y: number) => void;
  updateFloatingSize: (id: string, w: number, h: number) => void;
  removeFloating: (id: string) => void;

  // Maximize
  maximizePane: (paneId: string) => void;
  restorePane: () => void;

  // Layout tabs
  createLayout: () => void;
  renameLayout: (id: string, name: string) => void;
  duplicateLayout: (id: string) => void;
  deleteLayout: (id: string) => void;
  switchLayout: (id: string) => void;

  updateChannelContext: (
    color: ChannelColor,
    context: Partial<ChannelContext>,
  ) => void;
  updateGlobalContext: (context: Partial<ChannelContext>) => void;
  setTheme: (theme: Theme) => void;

  // Helpers
  getActiveLayout: () => LayoutTab;
}

type LayoutStore = WorkspaceState & LayoutActions;

function mutateActiveLayout(
  state: WorkspaceState,
  fn: (layout: LayoutTab) => Partial<LayoutTab>,
): Partial<WorkspaceState> {
  return {
    layouts: state.layouts.map((l) =>
      l.id === state.activeLayoutId ? { ...l, ...fn(l) } : l,
    ),
  };
}

function mutateNode(
  root: LayoutNode,
  targetId: string,
  fn: (node: LayoutNode) => LayoutNode,
): LayoutNode {
  if (root.id === targetId) return fn(root);
  if (root.type === "split") {
    return {
      ...root,
      children: root.children.map((child) => mutateNode(child, targetId, fn)),
    };
  }
  return root;
}

export const useLayoutStore = create<LayoutStore>()(
  persist(
    (set, get) => ({
      // ─── Initial state ───────────────────────────────────────
      layouts: [createDefaultLayout()],
      activeLayoutId: "",
      maximizedPaneId: null,
      channelContexts: {
        blue: {},
        red: {},
        green: {},
        yellow: {},
      },
      globalContext: {},
      theme: "dark",

      // ─── Tree mutations ──────────────────────────────────────

      splitPane: (paneId, direction, widgetType) => {
        set((state) => {
          const layout = state.layouts.find(
            (l) => l.id === state.activeLayoutId,
          );
          if (!layout) return state;

          const newPane = createPane(widgetType ?? "screener");

          const newRoot = mutateNode(layout.root, paneId, (node) => {
            const split: SplitNode = {
              type: "split",
              id: uid(),
              direction,
              children: [node, newPane],
              sizes: [0.5, 0.5],
            };
            return split;
          });

          return mutateActiveLayout(state, () => ({ root: newRoot }));
        });
      },

      addTab: (paneId, widgetType) => {
        set((state) => {
          const layout = state.layouts.find(
            (l) => l.id === state.activeLayoutId,
          );
          if (!layout) return state;

          const def = getWidget(widgetType);
          const newTab: WidgetInstance = {
            id: uid(),
            widgetType,
            title: def?.title ?? widgetType,
            settings: def?.defaultSettings ?? {},
            channelColor: null,
          };

          const newRoot = mutateNode(layout.root, paneId, (node) => {
            if (node.type !== "pane") return node;
            return {
              ...node,
              tabs: [...node.tabs, newTab],
              activeTabIndex: node.tabs.length,
            };
          });

          return mutateActiveLayout(state, () => ({ root: newRoot }));
        });
      },

      removeTab: (paneId, tabId) => {
        set((state) => {
          const layout = state.layouts.find(
            (l) => l.id === state.activeLayoutId,
          );
          if (!layout) return state;

          const pane = findNode(layout.root, paneId);
          if (!pane || pane.type !== "pane") return state;

          const newTabs = pane.tabs.filter((t) => t.id !== tabId);
          if (newTabs.length === 0) {
            // Remove the entire pane
            const newRoot = removeNode(layout.root, paneId);
            return mutateActiveLayout(state, () => ({
              root: newRoot ?? createPane("screener"),
            }));
          }

          const newRoot = mutateNode(layout.root, paneId, (node) => {
            if (node.type !== "pane") return node;
            return {
              ...node,
              tabs: newTabs,
              activeTabIndex: Math.min(node.activeTabIndex, newTabs.length - 1),
            };
          });

          return mutateActiveLayout(state, () => ({ root: newRoot }));
        });
      },

      setActiveTab: (paneId, index) => {
        set((state) => {
          const layout = state.layouts.find(
            (l) => l.id === state.activeLayoutId,
          );
          if (!layout) return state;

          const newRoot = mutateNode(layout.root, paneId, (node) => {
            if (node.type !== "pane") return node;
            return { ...node, activeTabIndex: index };
          });

          return mutateActiveLayout(state, () => ({ root: newRoot }));
        });
      },

      moveTab: (fromPaneId, tabId, toPaneId, zone) => {
        set((state) => {
          const layout = state.layouts.find(
            (l) => l.id === state.activeLayoutId,
          );
          if (!layout) return state;

          // Find the source tab
          const fromPane = findNode(layout.root, fromPaneId) as PaneNode | null;
          if (!fromPane || fromPane.type !== "pane") return state;
          const tab = fromPane.tabs.find((t) => t.id === tabId);
          if (!tab) return state;

          const isSamePane = fromPaneId === toPaneId;

          // ─── Same-pane drop ───────────────────────────────────
          if (isSamePane) {
            if (zone === "center") {
              return state; // No-op: tab is already here
            }

            const direction: "horizontal" | "vertical" =
              zone === "north" || zone === "south" ? "horizontal" : "vertical";

            if (fromPane.tabs.length === 1) {
              // Single tab → clone it (can't remove the only tab)
              const clonedTab: WidgetInstance = {
                ...tab,
                id: uid(),
                settings: { ...tab.settings },
                channelColor: tab.channelColor,
              };
              const clonedPane: PaneNode = {
                type: "pane",
                id: uid(),
                tabs: [clonedTab],
                activeTabIndex: 0,
              };

              const newRoot = mutateNode(layout.root, fromPaneId, (node) => {
                const first =
                  zone === "north" || zone === "west" ? clonedPane : node;
                const second =
                  zone === "north" || zone === "west" ? node : clonedPane;
                return {
                  type: "split",
                  id: uid(),
                  direction,
                  children: [first, second],
                  sizes: [0.5, 0.5],
                } as SplitNode;
              });

              return mutateActiveLayout(state, () => ({ root: newRoot }));
            } else {
              // Multi-tab → move the tab out into a new split pane
              const movedPane: PaneNode = {
                type: "pane",
                id: uid(),
                tabs: [tab],
                activeTabIndex: 0,
              };

              const newRoot = mutateNode(layout.root, fromPaneId, (node) => {
                if (node.type !== "pane") return node;
                const remaining = node.tabs.filter((t) => t.id !== tabId);
                const updatedSource: PaneNode = {
                  ...node,
                  tabs: remaining,
                  activeTabIndex: Math.min(
                    node.activeTabIndex,
                    remaining.length - 1,
                  ),
                };
                const first =
                  zone === "north" || zone === "west"
                    ? movedPane
                    : updatedSource;
                const second =
                  zone === "north" || zone === "west"
                    ? updatedSource
                    : movedPane;
                return {
                  type: "split",
                  id: uid(),
                  direction,
                  children: [first, second],
                  sizes: [0.5, 0.5],
                } as SplitNode;
              });

              return mutateActiveLayout(state, () => ({ root: newRoot }));
            }
          }

          // ─── Cross-pane drop ──────────────────────────────────

          // Remove tab from source
          let newRoot = layout.root;
          const remainingTabs = fromPane.tabs.filter((t) => t.id !== tabId);
          if (remainingTabs.length === 0) {
            const removed = removeNode(newRoot, fromPaneId);
            newRoot = removed ?? createPane("screener");
          } else {
            newRoot = mutateNode(newRoot, fromPaneId, (node) => {
              if (node.type !== "pane") return node;
              return {
                ...node,
                tabs: remainingTabs,
                activeTabIndex: Math.min(
                  node.activeTabIndex,
                  remainingTabs.length - 1,
                ),
              };
            });
          }

          if (zone === "center") {
            // Add as tab to target pane
            newRoot = mutateNode(newRoot, toPaneId, (node) => {
              if (node.type !== "pane") return node;
              return {
                ...node,
                tabs: [...node.tabs, tab],
                activeTabIndex: node.tabs.length,
              };
            });
          } else {
            // Split target pane
            const direction: "horizontal" | "vertical" =
              zone === "north" || zone === "south" ? "horizontal" : "vertical";
            const newPane: PaneNode = {
              type: "pane",
              id: uid(),
              tabs: [tab],
              activeTabIndex: 0,
            };

            newRoot = mutateNode(newRoot, toPaneId, (node) => {
              const first =
                zone === "north" || zone === "west" ? newPane : node;
              const second =
                zone === "north" || zone === "west" ? node : newPane;
              const split: SplitNode = {
                type: "split",
                id: uid(),
                direction,
                children: [first, second],
                sizes: [0.5, 0.5],
              };
              return split;
            });
          }

          return mutateActiveLayout(state, () => ({ root: newRoot }));
        });
      },

      resizeSplit: (splitId, sizes) => {
        set((state) => {
          const layout = state.layouts.find(
            (l) => l.id === state.activeLayoutId,
          );
          if (!layout) return state;

          const newRoot = mutateNode(layout.root, splitId, (node) => {
            if (node.type !== "split") return node;
            return { ...node, sizes };
          });

          return mutateActiveLayout(state, () => ({ root: newRoot }));
        });
      },

      removePane: (paneId) => {
        set((state) => {
          const layout = state.layouts.find(
            (l) => l.id === state.activeLayoutId,
          );
          if (!layout) return state;

          // Check if this pane is in a floating window
          const floatingIdx = layout.floatingWindows.findIndex(
            (fw) => fw.pane.id === paneId,
          );
          if (floatingIdx !== -1) {
            return mutateActiveLayout(state, () => ({
              floatingWindows: layout.floatingWindows.filter(
                (fw) => fw.pane.id !== paneId,
              ),
            }));
          }

          // Otherwise remove from tree
          const newRoot = removeNode(layout.root, paneId);
          return mutateActiveLayout(state, () => ({
            root: newRoot ?? createPane("screener"),
          }));
        });
      },

      updateWidgetSettings: (widgetId, patch) => {
        set((state) => {
          const layout = state.layouts.find(
            (l) => l.id === state.activeLayoutId,
          );
          if (!layout) return state;

          function updateInNode(node: LayoutNode): LayoutNode {
            if (node.type === "pane") {
              const updatedTabs = node.tabs.map((t) =>
                t.id === widgetId
                  ? { ...t, settings: { ...t.settings, ...patch } }
                  : t,
              );
              if (updatedTabs === node.tabs) return node;
              return { ...node, tabs: updatedTabs };
            }
            return {
              ...node,
              children: node.children.map(updateInNode),
            };
          }

          return mutateActiveLayout(state, (l) => ({
            root: updateInNode(l.root),
          }));
        });
      },

      // ─── Channel ─────────────────────────────────────────────

      setTabChannel: (tabId, color) => {
        set((state) => {
          const layout = state.layouts.find(
            (l) => l.id === state.activeLayoutId,
          );
          if (!layout) return state;

          function updateTabInNode(node: LayoutNode): LayoutNode {
            if (node.type === "pane") {
              const updatedTabs = node.tabs.map((t) =>
                t.id === tabId ? { ...t, channelColor: color } : t,
              );
              return { ...node, tabs: updatedTabs };
            }
            return {
              ...node,
              children: node.children.map(updateTabInNode),
            };
          }

          return mutateActiveLayout(state, (l) => ({
            root: updateTabInNode(l.root),
          }));
        });
      },

      // ─── Floating ────────────────────────────────────────────

      floatPane: (paneId) => {
        set((state) => {
          const layout = state.layouts.find(
            (l) => l.id === state.activeLayoutId,
          );
          if (!layout) return state;

          const pane = findNode(layout.root, paneId) as PaneNode | null;
          if (!pane || pane.type !== "pane") return state;

          // Move pane directly — preserve IDs so widgets stay mounted via portals
          const floating: FloatingWindow = {
            id: uid(),
            pane: { ...pane }, // shallow copy, same tab IDs
            x: 100,
            y: 100,
            w: 400,
            h: 300,
            zIndex: (layout.floatingWindows.length + 1) * 10,
          };

          const newRoot = removeNode(layout.root, paneId);

          return mutateActiveLayout(state, () => ({
            root: newRoot ?? createPane("screener"),
            floatingWindows: [...layout.floatingWindows, floating],
          }));
        });
      },

      dockPane: (floatingId, targetPaneId, zone) => {
        set((state) => {
          const layout = state.layouts.find(
            (l) => l.id === state.activeLayoutId,
          );
          if (!layout) return state;

          const fw = layout.floatingWindows.find((f) => f.id === floatingId);
          if (!fw) return state;

          let newRoot = layout.root;

          if (zone === "center") {
            // Add tabs to target
            newRoot = mutateNode(newRoot, targetPaneId, (node) => {
              if (node.type !== "pane") return node;
              return {
                ...node,
                tabs: [...node.tabs, ...fw.pane.tabs],
                activeTabIndex: node.tabs.length,
              };
            });
          } else {
            const direction: "horizontal" | "vertical" =
              zone === "north" || zone === "south" ? "horizontal" : "vertical";

            newRoot = mutateNode(newRoot, targetPaneId, (node) => {
              const first =
                zone === "north" || zone === "west" ? fw.pane : node;
              const second =
                zone === "north" || zone === "west" ? node : fw.pane;
              return {
                type: "split",
                id: uid(),
                direction,
                children: [first, second],
                sizes: [0.5, 0.5],
              } as SplitNode;
            });
          }

          return mutateActiveLayout(state, () => ({
            root: newRoot,
            floatingWindows: layout.floatingWindows.filter(
              (f) => f.id !== floatingId,
            ),
          }));
        });
      },

      updateFloatingPosition: (id, x, y) => {
        set((state) =>
          mutateActiveLayout(state, (l) => ({
            floatingWindows: l.floatingWindows.map((f) =>
              f.id === id ? { ...f, x, y } : f,
            ),
          })),
        );
      },

      updateFloatingSize: (id, w, h) => {
        set((state) =>
          mutateActiveLayout(state, (l) => ({
            floatingWindows: l.floatingWindows.map((f) =>
              f.id === id ? { ...f, w, h } : f,
            ),
          })),
        );
      },

      removeFloating: (id) => {
        set((state) =>
          mutateActiveLayout(state, (l) => ({
            floatingWindows: l.floatingWindows.filter((f) => f.id !== id),
          })),
        );
      },

      // ─── Maximize ────────────────────────────────────────────

      maximizePane: (paneId) => set({ maximizedPaneId: paneId }),
      restorePane: () => set({ maximizedPaneId: null }),

      // ─── Layout tabs ────────────────────────────────────────

      createLayout: () => {
        const newLayout = createDefaultLayout();
        set((state) => ({
          layouts: [...state.layouts, newLayout],
          activeLayoutId: newLayout.id,
        }));
      },

      renameLayout: (id, name) => {
        set((state) => ({
          layouts: state.layouts.map((l) => (l.id === id ? { ...l, name } : l)),
        }));
      },

      duplicateLayout: (id) => {
        set((state) => {
          const source = state.layouts.find((l) => l.id === id);
          if (!source) return state;

          const duplicatedRoot = recursiveGenerateIds(
            JSON.parse(JSON.stringify(source.root)),
          );

          const dup: LayoutTab = {
            id: uid(),
            name: `${source.name} (Copy)`,
            root: duplicatedRoot,
            floatingWindows: source.floatingWindows.map((fw) => ({
              ...fw,
              id: uid(),
              pane: recursiveGenerateIds(
                JSON.parse(JSON.stringify(fw.pane)),
              ) as PaneNode,
            })),
          };

          return {
            layouts: [...state.layouts, dup],
            activeLayoutId: dup.id,
          };
        });
      },

      deleteLayout: (id) => {
        set((state) => {
          if (state.layouts.length <= 1) return state;
          const filtered = state.layouts.filter((l) => l.id !== id);
          return {
            layouts: filtered,
            activeLayoutId:
              state.activeLayoutId === id
                ? filtered[0].id
                : state.activeLayoutId,
          };
        });
      },

      switchLayout: (id) => set({ activeLayoutId: id, maximizedPaneId: null }),

      updateChannelContext: (color, context) => {
        set((state) => ({
          channelContexts: {
            ...state.channelContexts,
            [color]: { ...state.channelContexts[color], ...context },
          },
        }));
      },

      updateGlobalContext: (context) => {
        set((state) => ({
          globalContext: { ...state.globalContext, ...context },
        }));
      },

      setTheme: (theme) => {
        document.documentElement.classList.remove("dark", "light");
        document.documentElement.classList.add(theme);
        set({ theme });
      },

      getActiveLayout: () => {
        const state = get();
        return (
          state.layouts.find((l) => l.id === state.activeLayoutId) ??
          state.layouts[0]
        );
      },
    }),
    {
      name: "terminal-layout",
      // Fix: set activeLayoutId on rehydrate if empty
      onRehydrateStorage: () => (state) => {
        if (
          state &&
          (!state.activeLayoutId ||
            !state.layouts.find((l) => l.id === state.activeLayoutId))
        ) {
          if (state.layouts.length === 0) {
            const def = createDefaultLayout();
            state.layouts = [def];
            state.activeLayoutId = def.id;
          } else {
            state.activeLayoutId = state.layouts[0].id;
          }
        }

        // Initialize channelContexts if missing
        if (state && !state.channelContexts) {
          state.channelContexts = {
            blue: {},
            red: {},
            green: {},
            yellow: {},
          };
        }

        // Initialize globalContext if missing
        if (state && !state.globalContext) {
          state.globalContext = {};
        }

        // Apply persisted theme to DOM
        if (state) {
          const theme = state.theme || "dark";
          document.documentElement.classList.remove("dark", "light");
          document.documentElement.classList.add(theme);
          if (!state.theme) state.theme = "dark";
        }
      },
    },
  ),
);

// Initialize activeLayoutId if not set
const initState = useLayoutStore.getState();
if (!initState.activeLayoutId && initState.layouts.length > 0) {
  useLayoutStore.setState({ activeLayoutId: initState.layouts[0].id });
}
