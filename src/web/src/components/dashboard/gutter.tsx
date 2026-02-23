import { useCallback, useRef, useState } from "react";
import type { SplitNode } from "@/types/layout";
import { useLayoutStore } from "@/stores/layout-store";

interface GutterProps {
  splitId: string;
  index: number; // gutter between children[index] and children[index+1]
  direction: SplitNode["direction"];
  sizes: number[];
}

export function Gutter({ splitId, index, direction, sizes }: GutterProps) {
  const resizeSplit = useLayoutStore((s) => s.resizeSplit);
  const containerRef = useRef<HTMLDivElement>(null);
  const [isDragging, setIsDragging] = useState(false);

  const handlePointerDown = useCallback(
    (e: React.PointerEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setIsDragging(true);

      const startPos = direction === "vertical" ? e.clientX : e.clientY;
      const container = containerRef.current?.parentElement;
      if (!container) return;

      const containerSize =
        direction === "vertical"
          ? container.offsetWidth
          : container.offsetHeight;

      const startSizes = [...sizes];

      const onMove = (moveEvent: PointerEvent) => {
        const currentPos =
          direction === "vertical" ? moveEvent.clientX : moveEvent.clientY;
        const delta = (currentPos - startPos) / containerSize;

        const newSizes = [...startSizes];
        newSizes[index] = Math.max(0.05, startSizes[index] + delta);
        newSizes[index + 1] = Math.max(0.05, startSizes[index + 1] - delta);

        // Normalize
        const total = newSizes.reduce((a, b) => a + b, 0);
        const normalized = newSizes.map((s) => s / total);

        requestAnimationFrame(() => {
          resizeSplit(splitId, normalized);
        });
      };

      const onUp = () => {
        setIsDragging(false);
        document.removeEventListener("pointermove", onMove);
        document.removeEventListener("pointerup", onUp);
      };

      document.addEventListener("pointermove", onMove);
      document.addEventListener("pointerup", onUp);
    },
    [splitId, index, direction, sizes, resizeSplit],
  );

  const isVertical = direction === "vertical";

  return (
    <div
      ref={containerRef}
      className={`
        relative shrink-0 z-10
        ${isVertical ? "w-1 cursor-col-resize" : "h-1 cursor-row-resize"}
        ${isDragging ? "bg-primary/50" : "bg-border hover:bg-primary/30"}
        transition-colors
      `}
      onPointerDown={handlePointerDown}
      style={{ touchAction: "none" }}
    >
      {/* Larger invisible hit area */}
      <div
        className={`absolute ${
          isVertical
            ? "top-0 bottom-0 -left-2 -right-2"
            : "left-0 right-0 -top-2 -bottom-2"
        }`}
      />
    </div>
  );
}
