import { useCallback, useState, memo } from "react";
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
import { AddWidgetDialog } from "./add-widget-dialog";
import {
  ContextMenu,
  ContextMenuContent,
  ContextMenuTrigger,
} from "@/components/ui/context-menu";
import { Maximize2, Minimize2, X, ExternalLink, Plus } from "lucide-react";

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

export const PaneContainer = memo(function PaneContainer({
  pane,
}: PaneContainerProps) {
  const maximizedPaneId = useLayoutStore((s) => s.maximizedPaneId);
  const isMaximized = maximizedPaneId === pane.id;
  const [addWidgetOpen, setAddWidgetOpen] = useState(false);

  const activeTab = pane.tabs[pane.activeTabIndex] ?? pane.tabs[0];
  if (!activeTab) return null;

  const handleDrop = useCallback(
    (item: DragItem, zone: DropZone) => {
      const tabId = item.tabId ?? item.paneId;
      useLayoutStore.getState().moveTab(item.paneId, tabId, pane.id, zone);
    },
    [pane.id],
  );

  const handleTabClick = useCallback(
    (i: number) => {
      useLayoutStore.getState().setActiveTab(pane.id, i);
    },
    [pane.id],
  );

  const handleTabClose = useCallback(
    (tabId: string) => {
      useLayoutStore.getState().removeTab(pane.id, tabId);
    },
    [pane.id],
  );

  const handleMaximize = useCallback(() => {
    const s = useLayoutStore.getState();
    s.maximizedPaneId === pane.id ? s.restorePane() : s.maximizePane(pane.id);
  }, [pane.id]);

  const handleFloat = useCallback(() => {
    useLayoutStore.getState().floatPane(pane.id);
  }, [pane.id]);

  const handleClose = useCallback(() => {
    useLayoutStore.getState().removePane(pane.id);
  }, [pane.id]);

  return (
    <DropCompass paneId={pane.id} onDrop={handleDrop}>
      <div className="flex flex-col h-full border border-border rounded-sm bg-card overflow-hidden">
        {/* ─── Header Chrome ─────────────────────────────────────── */}
        <PaneHeader
          pane={pane}
          isMaximized={isMaximized}
          onTabClick={handleTabClick}
          onTabClose={handleTabClose}
          onAddTab={() => setAddWidgetOpen(true)}
          onMaximize={handleMaximize}
          onFloat={handleFloat}
          onClose={handleClose}
        />

        {/* ─── Body: render ALL tabs, hide inactive with CSS ───── */}
        <div className="flex-1 overflow-hidden relative">
          {pane.tabs.map((tab, i) => {
            const def = getWidget(tab.widgetType);
            const Widget = def?.component;
            const isActive = i === pane.activeTabIndex;
            return (
              <div
                key={tab.id}
                className="absolute inset-0 overflow-auto"
                style={{ display: isActive ? "block" : "none" }}
              >
                {Widget ? (
                  <Widget
                    instanceId={tab.id}
                    settings={tab.settings}
                    onSettingsChange={(patch: Record<string, unknown>) =>
                      useLayoutStore
                        .getState()
                        .updateWidgetSettings(tab.id, patch)
                    }
                  />
                ) : (
                  <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
                    Widget "{tab.widgetType}" not registered
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Add Widget Dialog for this pane */}
      <AddWidgetDialog
        open={addWidgetOpen}
        onClose={() => setAddWidgetOpen(false)}
        targetPaneId={pane.id}
      />
    </DropCompass>
  );
});

// ─── Pane Header ───────────────────────────────────────────────────

interface PaneHeaderProps {
  pane: PaneNode;
  isMaximized: boolean;
  onTabClick: (index: number) => void;
  onTabClose: (tabId: string) => void;
  onAddTab: () => void;
  onMaximize: () => void;
  onFloat: () => void;
  onClose: () => void;
}

const PaneHeader = memo(function PaneHeader({
  pane,
  isMaximized,
  onTabClick,
  onTabClose,
  onAddTab,
  onMaximize,
  onFloat,
  onClose,
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
        {/* Add tab button */}
        <button
          onClick={onAddTab}
          className="p-1 rounded-sm text-muted-foreground hover:text-foreground hover:bg-muted transition-colors shrink-0"
          title="Add widget tab"
        >
          <Plus className="w-3 h-3" />
        </button>
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
});

// ─── Tab Button ────────────────────────────────────────────────────

interface TabButtonProps {
  paneId: string;
  tab: PaneNode["tabs"][number];
  isActive: boolean;
  onClick: () => void;
  onClose: () => void;
}

const TabButton = memo(function TabButton({
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

  const channelColor = tab.channelColor;
  const borderColor = channelColor ? CHANNEL_COLORS[channelColor] : null;

  const handleChannelChange = (color: ChannelColor | null) => {
    useLayoutStore.getState().setTabChannel(tab.id, color);
  };

  return (
    <ContextMenu>
      <ContextMenuTrigger asChild>
        <div
          ref={dragRef as unknown as React.Ref<HTMLDivElement>}
          className={`
            flex items-center gap-1 px-2 py-1 text-xs rounded-t-sm cursor-pointer
            min-w-0 max-w-[150px] group relative
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
          {/* Colored bottom border for channel link */}
          {borderColor && (
            <div
              className={`absolute bottom-0 left-1 right-1 h-0.5 rounded-full ${borderColor}`}
            />
          )}
        </div>
      </ContextMenuTrigger>
      <ContextMenuContent className="min-w-[140px]">
        <div className="px-2 py-1.5">
          <p className="text-xs font-medium text-muted-foreground mb-2">
            Symbol Link
          </p>
          <div className="flex items-center gap-1.5">
            {ALL_CHANNELS.map((c) => (
              <button
                key={c ?? "none"}
                onClick={() => handleChannelChange(c)}
                className={`
                  w-4 h-4 rounded-full border transition-all
                  ${c ? CHANNEL_COLORS[c] : "bg-muted"}
                  ${c === channelColor ? "ring-2 ring-primary ring-offset-1 ring-offset-background" : "border-border hover:scale-110"}
                `}
                title={c ?? "None"}
              />
            ))}
          </div>
        </div>
      </ContextMenuContent>
    </ContextMenu>
  );
});
