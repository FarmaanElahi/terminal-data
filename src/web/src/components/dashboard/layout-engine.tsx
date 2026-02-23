import { useState } from "react";
import { DndProvider } from "react-dnd";
import { HTML5Backend } from "react-dnd-html5-backend";
import { useLayoutStore } from "@/stores/layout-store";
import { LayoutNodeRenderer } from "./layout-node";
import { FloatingPanel } from "./floating-panel";
import { LayoutTabsBar } from "./layout-tabs-bar";
import { AddWidgetDialog } from "./add-widget-dialog";
import { PaneContainer } from "./pane-container";
import type { PaneNode, LayoutNode } from "@/types/layout";

/** Find a PaneNode by id in the tree */
function findPaneInTree(node: LayoutNode, id: string): PaneNode | null {
  if (node.type === "pane" && node.id === id) return node;
  if (node.type === "split") {
    for (const child of node.children) {
      const found = findPaneInTree(child, id);
      if (found) return found;
    }
  }
  return null;
}

export function LayoutEngine() {
  const layout = useLayoutStore((s) => s.getActiveLayout());
  const maximizedPaneId = useLayoutStore((s) => s.maximizedPaneId);
  const [addWidgetOpen, setAddWidgetOpen] = useState(false);

  // Find maximized pane if active
  const maximizedPane = maximizedPaneId
    ? findPaneInTree(layout.root, maximizedPaneId)
    : null;

  return (
    <DndProvider backend={HTML5Backend}>
      <div className="flex flex-col h-full w-full overflow-hidden">
        {/* Main grid area */}
        <div className="flex-1 relative overflow-hidden">
          {/* Normal layout tree */}
          <div className={`w-full h-full ${maximizedPane ? "invisible" : ""}`}>
            <LayoutNodeRenderer node={layout.root} />
          </div>

          {/* Maximized pane overlay */}
          {maximizedPane && (
            <div className="absolute inset-0 z-40 bg-background">
              <PaneContainer pane={maximizedPane} />
            </div>
          )}

          {/* Floating windows */}
          {layout.floatingWindows.map((fw) => (
            <FloatingPanel key={fw.id} fw={fw} />
          ))}
        </div>

        {/* Bottom layout tabs bar */}
        <LayoutTabsBar />

        {/* Add widget dialog */}
        <AddWidgetDialog
          open={addWidgetOpen}
          onClose={() => setAddWidgetOpen(false)}
        />
      </div>
    </DndProvider>
  );
}
