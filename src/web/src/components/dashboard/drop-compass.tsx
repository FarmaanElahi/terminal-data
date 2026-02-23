import { useState } from "react";
import { useDrop } from "react-dnd";
import type { DropZone, DragItem } from "@/types/layout";

interface DropCompassProps {
  paneId: string;
  onDrop: (item: DragItem, zone: DropZone) => void;
  children: React.ReactNode;
}

const ZONE_CLASSES: Record<DropZone, string> = {
  north: "top-0 left-0 right-0 h-1/4",
  south: "bottom-0 left-0 right-0 h-1/4",
  west: "top-1/4 bottom-1/4 left-0 w-1/4",
  east: "top-1/4 bottom-1/4 right-0 w-1/4",
  center: "top-1/4 bottom-1/4 left-1/4 right-1/4",
};

const ZONE_LABELS: Record<DropZone, string> = {
  north: "↑",
  south: "↓",
  west: "←",
  east: "→",
  center: "⊞",
};

export function DropCompass({ paneId, onDrop, children }: DropCompassProps) {
  const [activeZone, setActiveZone] = useState<DropZone | null>(null);

  const [{ isOver, canDrop }, dropRef] = useDrop(
    () => ({
      accept: ["pane", "tab"],
      drop: (item: DragItem, monitor) => {
        if (monitor.didDrop()) return; // child already handled
        if (activeZone) {
          onDrop(item, activeZone);
        }
      },
      canDrop: (item: DragItem) => item.paneId !== paneId,
      collect: (monitor) => ({
        isOver: monitor.isOver({ shallow: true }),
        canDrop: monitor.canDrop(),
      }),
    }),
    [paneId, activeZone, onDrop],
  );

  const showCompass = isOver && canDrop;

  return (
    <div
      ref={dropRef as unknown as React.Ref<HTMLDivElement>}
      className="relative w-full h-full"
    >
      {children}

      {showCompass && (
        <div className="absolute inset-0 z-50 pointer-events-auto">
          {(Object.entries(ZONE_CLASSES) as [DropZone, string][]).map(
            ([zone, classes]) => (
              <div
                key={zone}
                className={`absolute ${classes} flex items-center justify-center`}
                onPointerEnter={() => setActiveZone(zone)}
                onPointerLeave={() =>
                  setActiveZone((prev) => (prev === zone ? null : prev))
                }
              >
                <div
                  className={`
                    w-full h-full rounded-sm border-2 border-dashed transition-all
                    flex items-center justify-center
                    ${
                      activeZone === zone
                        ? "bg-primary/20 border-primary"
                        : "bg-transparent border-transparent hover:bg-muted/30 hover:border-muted-foreground/30"
                    }
                  `}
                >
                  <span
                    className={`
                      text-lg font-bold select-none
                      ${activeZone === zone ? "text-primary" : "text-muted-foreground/30"}
                    `}
                  >
                    {ZONE_LABELS[zone]}
                  </span>
                </div>
              </div>
            ),
          )}
        </div>
      )}
    </div>
  );
}
