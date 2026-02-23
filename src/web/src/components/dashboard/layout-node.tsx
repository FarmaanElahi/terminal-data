import type { LayoutNode } from "@/types/layout";
import { PaneContainer } from "./pane-container";
import { Gutter } from "./gutter";

interface LayoutNodeRendererProps {
  node: LayoutNode;
}

/**
 * Recursively renders the layout tree.
 * SplitNode → flex container with gutters between children.
 * PaneNode → PaneContainer (chrome + widget).
 */
export function LayoutNodeRenderer({ node }: LayoutNodeRendererProps) {
  if (node.type === "pane") {
    return <PaneContainer pane={node} />;
  }

  // SplitNode
  const isVertical = node.direction === "vertical";

  return (
    <div
      className={`flex ${isVertical ? "flex-row" : "flex-col"} w-full h-full`}
    >
      {node.children.map((child, i) => (
        <div key={child.id} className="contents">
          <div
            style={{
              flex: `${node.sizes[i]} 1 0%`,
              minWidth: isVertical ? 50 : undefined,
              minHeight: !isVertical ? 50 : undefined,
              overflow: "hidden",
            }}
          >
            <LayoutNodeRenderer node={child} />
          </div>
          {i < node.children.length - 1 && (
            <Gutter
              splitId={node.id}
              index={i}
              direction={node.direction}
              sizes={node.sizes}
            />
          )}
        </div>
      ))}
    </div>
  );
}
