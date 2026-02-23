import { useCallback } from "react";
import { useDrag } from "react-dnd";
import type {
  PaneNode,
  DragItem,
  DropZone,
  ChannelColor,
} from "@/types/layout";
import { useLayoutStore } from "@/stores/layout-store";
import { getWidget } from "@/lib/widget-registry";
import { DropCompass } from "./drop-compass";
import { Maximize2, Minimize2, X, ExternalLink } from "lucide-react";

const CHANNEL_COLORS: Record<ChannelColor, string> = {
  blue: "bg-blue-500",
  red: "bg-red-500",
  green: "bg-green-500",
  yellow: "bg-yellow-500",
};

const ALL_CHANNELS: (ChannelColor | null)[] = [
  null,
  "blue",
  "red",
  "green",
  "yellow",
];

interface PaneContainerProps {
  pane: PaneNode;
}

export function PaneContainer({ pane }: PaneContainerProps) {
  const {
    setActiveTab,
    removeTab,
    removePane,
    maximizePane,
    restorePane,
    floatPane,
    moveTab,
    setPaneChannel,
  } = useLayoutStore();
  const maximizedPaneId = useLayoutStore((s) => s.maximizedPaneId);
  const isMaximized = maximizedPaneId === pane.id;

  const activeTab = pane.tabs[pane.activeTabIndex] ?? pane.tabs[0];
  if (!activeTab) return null;

  const widgetDef = getWidget(activeTab.widgetType);
  const WidgetComponent = widgetDef?.component;

  const handleDrop = useCallback(
    (item: DragItem, zone: DropZone) => {
      const tabId = item.tabId ?? item.paneId; // If dragging a pane, move its active tab
      moveTab(item.paneId, tabId, pane.id, zone);
    },
    [moveTab, pane.id],
  );

  const handleSettingsChange = useCallback(
    (patch: Record<string, unknown>) => {
      useLayoutStore.getState().updateWidgetSettings(activeTab.id, patch);
    },
    [activeTab.id],
  );

  return (
    <DropCompass paneId={pane.id} onDrop={handleDrop}>
      <div className="flex flex-col h-full border border-border rounded-sm bg-card overflow-hidden">
        {/* ─── Header Chrome ─────────────────────────────────────── */}
        <PaneHeader
          pane={pane}
          isMaximized={isMaximized}
          onTabClick={(i) => setActiveTab(pane.id, i)}
          onTabClose={(tabId) => removeTab(pane.id, tabId)}
          onMaximize={() =>
            isMaximized ? restorePane() : maximizePane(pane.id)
          }
          onFloat={() => floatPane(pane.id)}
          onClose={() => removePane(pane.id)}
          onChannelChange={(color) => setPaneChannel(pane.id, color)}
        />

        {/* ─── Body ──────────────────────────────────────────────── */}
        <div className="flex-1 overflow-auto">
          {WidgetComponent ? (
            <WidgetComponent
              instanceId={activeTab.id}
              settings={activeTab.settings}
              onSettingsChange={handleSettingsChange}
            />
          ) : (
            <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
              Widget "{activeTab.widgetType}" not registered
            </div>
          )}
        </div>
      </div>
    </DropCompass>
  );
}

// ─── Pane Header ───────────────────────────────────────────────────

interface PaneHeaderProps {
  pane: PaneNode;
  isMaximized: boolean;
  onTabClick: (index: number) => void;
  onTabClose: (tabId: string) => void;
  onMaximize: () => void;
  onFloat: () => void;
  onClose: () => void;
  onChannelChange: (color: ChannelColor | null) => void;
}

function PaneHeader({
  pane,
  isMaximized,
  onTabClick,
  onTabClose,
  onMaximize,
  onFloat,
  onClose,
  onChannelChange,
}: PaneHeaderProps) {
  // Drag the whole pane
  const [{ isDragging }, dragRef] = useDrag(
    () => ({
      type: "pane",
      item: (): DragItem => ({
        type: "pane",
        paneId: pane.id,
        tabId: pane.tabs[pane.activeTabIndex]?.id,
      }),
      collect: (monitor) => ({
        isDragging: monitor.isDragging(),
      }),
    }),
    [pane.id, pane.activeTabIndex],
  );

  return (
    <div
      ref={dragRef as unknown as React.Ref<HTMLDivElement>}
      className={`
        flex items-center gap-0.5 h-8 bg-muted/50 border-b border-border
        select-none shrink-0 px-1
        ${isDragging ? "opacity-40" : ""}
      `}
    >
      {/* Channel indicator */}
      <ChannelDot color={pane.channelColor} onChange={onChannelChange} />

      {/* Tabs */}
      <div className="flex-1 flex items-center gap-0.5 overflow-x-auto scrollbar-none min-w-0">
        {pane.tabs.map((tab, i) => (
          <TabButton
            key={tab.id}
            paneId={pane.id}
            tab={tab}
            isActive={i === pane.activeTabIndex}
            onClick={() => onTabClick(i)}
            onClose={() => onTabClose(tab.id)}
          />
        ))}
      </div>

      {/* Controls */}
      <div className="flex items-center gap-0.5 shrink-0">
        <button
          onClick={onFloat}
          className="p-1 rounded-sm text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
          title="Pop out"
        >
          <ExternalLink className="w-3 h-3" />
        </button>
        <button
          onClick={onMaximize}
          className="p-1 rounded-sm text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
          title={isMaximized ? "Restore" : "Maximize"}
        >
          {isMaximized ? (
            <Minimize2 className="w-3 h-3" />
          ) : (
            <Maximize2 className="w-3 h-3" />
          )}
        </button>
        <button
          onClick={onClose}
          className="p-1 rounded-sm text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors"
          title="Close"
        >
          <X className="w-3 h-3" />
        </button>
      </div>
    </div>
  );
}

// ─── Tab Button ────────────────────────────────────────────────────

interface TabButtonProps {
  paneId: string;
  tab: PaneNode["tabs"][number];
  isActive: boolean;
  onClick: () => void;
  onClose: () => void;
}

function TabButton({
  paneId,
  tab,
  isActive,
  onClick,
  onClose,
}: TabButtonProps) {
  const [{ isDragging }, dragRef] = useDrag(
    () => ({
      type: "tab",
      item: (): DragItem => ({
        type: "tab",
        paneId,
        tabId: tab.id,
      }),
      collect: (monitor) => ({
        isDragging: monitor.isDragging(),
      }),
    }),
    [paneId, tab.id],
  );

  return (
    <div
      ref={dragRef as unknown as React.Ref<HTMLDivElement>}
      className={`
        flex items-center gap-1 px-2 py-1 text-xs rounded-t-sm cursor-pointer
        min-w-0 max-w-[150px] group
        ${isDragging ? "opacity-40" : ""}
        ${
          isActive
            ? "bg-card text-foreground border-t border-x border-border"
            : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
        }
      `}
      onClick={onClick}
    >
      <span className="truncate">{tab.title}</span>
      <button
        onClick={(e) => {
          e.stopPropagation();
          onClose();
        }}
        className="shrink-0 opacity-0 group-hover:opacity-100 p-0.5 rounded-sm hover:bg-muted transition-all"
      >
        <X className="w-2.5 h-2.5" />
      </button>
    </div>
  );
}

// ─── Channel Dot ───────────────────────────────────────────────────

interface ChannelDotProps {
  color: ChannelColor | null;
  onChange: (color: ChannelColor | null) => void;
}

function ChannelDot({ color, onChange }: ChannelDotProps) {
  return (
    <div className="relative group shrink-0">
      <button
        className={`
          w-3 h-3 rounded-full border border-border transition-colors
          ${color ? CHANNEL_COLORS[color] : "bg-muted"}
        `}
        title={color ? `Channel: ${color}` : "No channel"}
      />
      {/* Dropdown on hover */}
      <div className="absolute top-full left-0 mt-1 hidden group-hover:flex gap-1 bg-popover border border-border rounded-md p-1 shadow-lg z-50">
        {ALL_CHANNELS.map((c) => (
          <button
            key={c ?? "none"}
            onClick={() => onChange(c)}
            className={`
              w-4 h-4 rounded-full border transition-all
              ${c ? CHANNEL_COLORS[c] : "bg-muted"}
              ${c === color ? "ring-2 ring-primary ring-offset-1 ring-offset-background" : "border-border hover:scale-110"}
            `}
            title={c ?? "None"}
          />
        ))}
      </div>
    </div>
  );
}
