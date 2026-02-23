# Dashboard Layout Engine — Architecture

## Overview

A recursive tiling window manager for the web. Content-agnostic — it manages pane layout, DnD, and persistence while widgets fill each pane.

## Data Model

```
Workspace
├── LayoutTab[] (bottom bar — only one active at a time)
│   ├── root: LayoutNode (recursive tree)
│   │   ├── SplitNode (branch) — direction + children[] + sizes[]
│   │   │   ├── SplitNode ...
│   │   │   └── PaneNode (leaf) — tabs[] + activeTabIndex + channelColor
│   │   │       ├── WidgetInstance { id, widgetType, title, settings }
│   │   │       └── WidgetInstance ...
│   │   └── PaneNode ...
│   └── floatingWindows: FloatingWindow[]
└── maximizedPaneId: string | null
```

### Key Types (`types/layout.ts`)

| Type             | Role                                                                 |
| ---------------- | -------------------------------------------------------------------- |
| `SplitNode`      | Branch — splits children horizontally or vertically with flex ratios |
| `PaneNode`       | Leaf — holds a tab stack of `WidgetInstance`s                        |
| `WidgetInstance` | A single widget with its type, title, and serializable settings      |
| `FloatingWindow` | A detached pane with absolute position (x, y, w, h, zIndex)          |
| `LayoutTab`      | A named layout configuration (tree + floating windows)               |

## Component Hierarchy

```
LayoutEngine (DndProvider)
├── LayoutNodeRenderer (recursive)
│   ├── SplitNode → flex container
│   │   ├── LayoutNodeRenderer (child 1)
│   │   ├── Gutter (resizable divider)
│   │   └── LayoutNodeRenderer (child 2)
│   └── PaneNode → PaneContainer
│       ├── PaneHeader (drag handle, tab strip, channel dot, controls)
│       │   └── TabButton (draggable individual tab)
│       ├── DropCompass (5-zone DnD overlay on drag-over)
│       └── WidgetComponent (from registry)
├── FloatingPanel[] (absolute positioned, draggable, resizable)
│   └── PaneContainer
└── LayoutTabsBar (bottom bar for switching layouts)
```

## State Management (`stores/layout-store.ts`)

Zustand store with `persist` middleware → `localStorage` key: `terminal-layout`.

### Tree Mutations

All mutations are immutable — they create new tree nodes via `mutateNode()` (recursive find-and-replace) and `removeNode()` (prune + collapse single-child splits).

| Action                              | Description                                      |
| ----------------------------------- | ------------------------------------------------ |
| `splitPane(id, dir)`                | Wraps a pane in a new SplitNode with a sibling   |
| `addTab(paneId, type)`              | Adds a widget tab to a pane's tab stack          |
| `removeTab(paneId, tabId)`          | Removes a tab; collapses pane if empty           |
| `moveTab(from, tabId, to, zone)`    | DnD result — merges (center) or splits (N/S/E/W) |
| `resizeSplit(id, sizes)`            | Updates flex ratios from gutter drag             |
| `floatPane(id)`                     | Detaches pane from tree → floating window        |
| `dockPane(floatId, targetId, zone)` | Re-inserts floating window into tree             |

## Drag & Drop (`react-dnd`)

### Drag Sources

- **Pane header** (`type: "pane"`) — moves entire pane
- **Tab button** (`type: "tab"`) — moves single tab

### Drop Target: DropCompass

5-zone overlay appears when dragging over a PaneContainer:

```
┌─────────────────┐
│      North      │
├────┬───────┬────┤
│    │       │    │
│ W  │ Center│  E │
│    │       │    │
├────┴───────┴────┤
│      South      │
└─────────────────┘
```

- **N/S/E/W** → creates a new SplitNode around the target
- **Center** → adds as a tab in the target pane

## Channel Linking (`lib/channel-bus.ts`)

Simple pub/sub bus with 4 color channels: `blue`, `red`, `green`, `yellow`.

- Each pane can be assigned a channel via the colored dot in its header
- Widgets broadcast events via `useWidget().broadcast(type, payload)`
- Widgets listen via `useWidget().useChannelEvent(handler)`
- Events from the same `sourceId` are filtered out (no self-echo)

**Example flow:** Watchlist (blue) clicks "AAPL" → broadcasts `{type: "context_change", payload: {symbol: "AAPL"}}` → Chart (blue) receives and updates its symbol.

## Widget Framework

### Registry (`lib/widget-registry.ts`)

Maps `widgetType` string → `{ component, title, icon, defaultSettings }`.
All widgets registered in `lib/register-widgets.ts` (imported in `main.tsx`).

### Widget Contract (`WidgetProps`)

```ts
interface WidgetProps {
  instanceId: string;
  settings: Record<string, unknown>;
  onSettingsChange: (patch: Record<string, unknown>) => void;
}
```

### Adding a New Widget

1. Create `components/widgets/my-widget.tsx` implementing `WidgetProps`
2. Add `registerWidget({...})` call in `lib/register-widgets.ts`
3. Done — it appears in the Add Widget dialog automatically

## Persistence

Layout state is serialized to `localStorage` under key `terminal-layout` via Zustand's `persist` middleware. On rehydrate, if `activeLayoutId` is stale, it falls back to the first layout or creates a default.

## File Map

```
components/dashboard/
├── ARCHITECTURE.md          ← you are here
├── layout-engine.tsx        # Top-level: DndProvider + tree + floats
├── layout-node.tsx          # Recursive SplitNode/PaneNode renderer
├── gutter.tsx               # Resizable divider (pointer events + rAF)
├── pane-container.tsx       # Chrome: tabs, channel dot, controls
├── drop-compass.tsx         # 5-zone react-dnd drop overlay
├── floating-panel.tsx       # Draggable/resizable floating window
├── layout-tabs-bar.tsx      # Bottom bar for layout switching
└── add-widget-dialog.tsx    # Widget picker dialog
```
