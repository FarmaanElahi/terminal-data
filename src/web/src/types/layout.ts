// ─── Layout Tree Types ─────────────────────────────────────────────

export type LayoutNode = SplitNode | PaneNode;

export interface SplitNode {
  type: "split";
  id: string;
  direction: "horizontal" | "vertical";
  children: LayoutNode[];
  sizes: number[]; // flex ratios, must sum to 1
}

export interface PaneNode {
  type: "pane";
  id: string;
  tabs: WidgetInstance[];
  activeTabIndex: number;
}

export interface WidgetInstance {
  id: string;
  widgetType: string;
  title: string;
  settings: Record<string, unknown>;
  channelColor: ChannelColor | null;
}

// ─── Floating Windows ──────────────────────────────────────────────

export interface FloatingWindow {
  id: string;
  pane: PaneNode;
  x: number;
  y: number;
  w: number;
  h: number;
  zIndex: number;
}

// ─── Layout Tabs ───────────────────────────────────────────────────

export interface LayoutTab {
  id: string;
  name: string;
  root: LayoutNode;
  floatingWindows: FloatingWindow[];
}

export interface WorkspaceState {
  layouts: LayoutTab[];
  activeLayoutId: string;
  maximizedPaneId: string | null;
}

// ─── Channel Linking ───────────────────────────────────────────────

export type ChannelColor = "blue" | "red" | "green" | "yellow";

export interface ChannelEvent {
  type: string;
  payload: unknown;
  sourceId: string;
  channel: ChannelColor;
}

// ─── DnD ───────────────────────────────────────────────────────────

export type DropZone = "north" | "south" | "east" | "west" | "center";

export interface DragItem {
  type: "pane" | "tab";
  paneId: string;
  tabId?: string;
}

// ─── Widget Registry ───────────────────────────────────────────────

export interface WidgetProps {
  instanceId: string;
  settings: Record<string, unknown>;
  onSettingsChange: (patch: Record<string, unknown>) => void;
}

export interface WidgetDefinition {
  type: string;
  title: string;
  icon: string; // lucide icon name
  component: React.ComponentType<WidgetProps>;
  defaultSettings: Record<string, unknown>;
}
