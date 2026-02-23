import { useCallback, useRef, useState } from "react";
import { useDrop } from "react-dnd";
import type { DropZone, DragItem } from "@/types/layout";

interface DropCompassProps {
  paneId: string;
  onDrop: (item: DragItem, zone: DropZone) => void;
  children: React.ReactNode;
}

/**
 * Determines which drop zone a point falls in, relative to the container rect.
 * Uses a diamond/cross pattern like VSCode.
 */
function getZoneFromPoint(
  rect: DOMRect,
  clientX: number,
  clientY: number,
): DropZone {
  const x = (clientX - rect.left) / rect.width; // 0..1
  const y = (clientY - rect.top) / rect.height; // 0..1

  // Center zone: middle 40%
  if (x > 0.3 && x < 0.7 && y > 0.3 && y < 0.7) return "center";

  // Edge zones based on which edge is closest
  const distTop = y;
  const distBottom = 1 - y;
  const distLeft = x;
  const distRight = 1 - x;

  const min = Math.min(distTop, distBottom, distLeft, distRight);
  if (min === distTop) return "north";
  if (min === distBottom) return "south";
  if (min === distLeft) return "west";
  return "east";
}

export function DropCompass({ paneId, onDrop, children }: DropCompassProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [activeZone, setActiveZone] = useState<DropZone | null>(null);

  const handleHover = useCallback(
    (
      _item: DragItem,
      monitor: { getClientOffset: () => { x: number; y: number } | null },
    ) => {
      const offset = monitor.getClientOffset();
      const el = containerRef.current;
      if (!offset || !el) {
        setActiveZone(null);
        return;
      }
      const rect = el.getBoundingClientRect();
      const zone = getZoneFromPoint(rect, offset.x, offset.y);
      setActiveZone(zone);
    },
    [],
  );

  const [{ isOver, canDrop }, dropRef] = useDrop(
    () => ({
      accept: ["pane", "tab"],
      hover: handleHover,
      drop: (item: DragItem, monitor) => {
        if (monitor.didDrop()) return;
        const offset = monitor.getClientOffset();
        const el = containerRef.current;
        if (!offset || !el) return;
        const rect = el.getBoundingClientRect();
        const zone = getZoneFromPoint(rect, offset.x, offset.y);
        onDrop(item, zone);
      },
      canDrop: () => true, // Allow all drops — same-pane splits work too
      collect: (monitor) => ({
        isOver: monitor.isOver({ shallow: true }),
        canDrop: monitor.canDrop(),
      }),
    }),
    [paneId, onDrop, handleHover],
  );

  // Combine refs
  const setRefs = useCallback(
    (el: HTMLDivElement | null) => {
      containerRef.current = el;
      (dropRef as (el: HTMLDivElement | null) => void)(el);
    },
    [dropRef],
  );

  const showOverlay = isOver && canDrop;

  return (
    <div ref={setRefs} className="relative w-full h-full">
      {children}

      {/* Drop zone overlay — visible during drag */}
      {showOverlay && (
        <div className="absolute inset-0 z-50 pointer-events-none">
          {/* Full overlay tint */}
          <div className="absolute inset-0 bg-primary/5 border-2 border-primary/20 rounded-sm" />

          {/* Zone highlights */}
          {activeZone === "north" && (
            <div className="absolute top-0 left-0 right-0 h-1/2 bg-primary/15 border-b-2 border-primary rounded-t-sm flex items-center justify-center">
              <div className="bg-primary text-primary-foreground text-xs font-medium px-2 py-0.5 rounded shadow">
                ↑ Split Top
              </div>
            </div>
          )}
          {activeZone === "south" && (
            <div className="absolute bottom-0 left-0 right-0 h-1/2 bg-primary/15 border-t-2 border-primary rounded-b-sm flex items-center justify-center">
              <div className="bg-primary text-primary-foreground text-xs font-medium px-2 py-0.5 rounded shadow">
                ↓ Split Bottom
              </div>
            </div>
          )}
          {activeZone === "west" && (
            <div className="absolute top-0 left-0 bottom-0 w-1/2 bg-primary/15 border-r-2 border-primary rounded-l-sm flex items-center justify-center">
              <div className="bg-primary text-primary-foreground text-xs font-medium px-2 py-0.5 rounded shadow">
                ← Split Left
              </div>
            </div>
          )}
          {activeZone === "east" && (
            <div className="absolute top-0 right-0 bottom-0 w-1/2 bg-primary/15 border-l-2 border-primary rounded-r-sm flex items-center justify-center">
              <div className="bg-primary text-primary-foreground text-xs font-medium px-2 py-0.5 rounded shadow">
                → Split Right
              </div>
            </div>
          )}
          {activeZone === "center" && (
            <div className="absolute inset-2 bg-primary/15 border-2 border-primary border-dashed rounded-sm flex items-center justify-center">
              <div className="bg-primary text-primary-foreground text-xs font-medium px-2 py-0.5 rounded shadow">
                ⊞ Add as Tab
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
