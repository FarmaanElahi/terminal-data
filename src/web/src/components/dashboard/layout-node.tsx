import { Group, Panel, Separator } from "react-resizable-panels";
import type { LayoutNode } from "@/types/layout";
import { PaneContainer } from "./pane-container";

interface LayoutNodeRendererProps {
  node: LayoutNode;
}

/**
 * Recursively renders the layout tree.
 * SplitNode → react-resizable-panels Group with Separator handles.
 * PaneNode → PaneContainer (chrome + widget).
 */
export function LayoutNodeRenderer({ node }: LayoutNodeRendererProps) {
  if (node.type === "pane") {
    return <PaneContainer pane={node} />;
  }

  // SplitNode — our "vertical" split means side-by-side → horizontal orientation
  const orientation = node.direction === "vertical" ? "horizontal" : "vertical";
  const isHorizontal = orientation === "horizontal";

  // Build alternating Panel + Separator children (no wrapping div — react-resizable-panels needs flat children)
  const elements: React.ReactNode[] = [];
  node.children.forEach((child, i) => {
    elements.push(
      <Panel
        key={child.id}
        defaultSize={node.sizes[i] * 100}
        minSize={5}
        className="overflow-hidden"
      >
        <LayoutNodeRenderer node={child} />
      </Panel>,
    );
    if (i < node.children.length - 1) {
      elements.push(
        <Separator
          key={`sep-${child.id}`}
          className={`
            relative flex items-center justify-center
            ${isHorizontal ? "w-1.5" : "h-1.5"}
            bg-border
            hover:bg-primary/30 active:bg-primary/50
            transition-colors cursor-${isHorizontal ? "col" : "row"}-resize
          `}
        >
          {/* Grip indicator */}
          <div
            className={`
              ${isHorizontal ? "w-0.5 h-8" : "h-0.5 w-8"}
              bg-muted-foreground/20 rounded-full
              group-hover:bg-primary/50
            `}
          />
        </Separator>,
      );
    }
  });

  return (
    <Group
      orientation={orientation as "horizontal" | "vertical"}
      className="w-full h-full"
    >
      {elements}
    </Group>
  );
}
