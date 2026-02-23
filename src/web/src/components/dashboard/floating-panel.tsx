import { useCallback, useRef, useState } from "react";
import type { FloatingWindow as FloatingWindowType } from "@/types/layout";
import { useLayoutStore } from "@/stores/layout-store";
import { PaneContainer } from "./pane-container";
import { GripHorizontal } from "lucide-react";

interface FloatingPanelProps {
  fw: FloatingWindowType;
}

export function FloatingPanel({ fw }: FloatingPanelProps) {
  const { updateFloatingPosition, updateFloatingSize } = useLayoutStore();
  const panelRef = useRef<HTMLDivElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isResizing, setIsResizing] = useState(false);

  const handleDragStart = useCallback(
    (e: React.PointerEvent) => {
      e.preventDefault();
      setIsDragging(true);
      const startX = e.clientX - fw.x;
      const startY = e.clientY - fw.y;

      const onMove = (me: PointerEvent) => {
        requestAnimationFrame(() => {
          updateFloatingPosition(
            fw.id,
            me.clientX - startX,
            me.clientY - startY,
          );
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
    [fw.id, fw.x, fw.y, updateFloatingPosition],
  );

  const handleResizeStart = useCallback(
    (e: React.PointerEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setIsResizing(true);
      const startX = e.clientX;
      const startY = e.clientY;
      const startW = fw.w;
      const startH = fw.h;

      const onMove = (me: PointerEvent) => {
        const newW = Math.max(200, startW + (me.clientX - startX));
        const newH = Math.max(150, startH + (me.clientY - startY));
        requestAnimationFrame(() => {
          updateFloatingSize(fw.id, newW, newH);
        });
      };
      const onUp = () => {
        setIsResizing(false);
        document.removeEventListener("pointermove", onMove);
        document.removeEventListener("pointerup", onUp);
      };
      document.addEventListener("pointermove", onMove);
      document.addEventListener("pointerup", onUp);
    },
    [fw.id, fw.w, fw.h, updateFloatingSize],
  );

  return (
    <div
      ref={panelRef}
      className={`absolute shadow-2xl rounded-md overflow-hidden border border-border bg-card ${isDragging ? "opacity-80 cursor-grabbing" : ""} ${isResizing ? "cursor-se-resize" : ""}`}
      style={{
        left: fw.x,
        top: fw.y,
        width: fw.w,
        height: fw.h,
        zIndex: fw.zIndex,
      }}
    >
      <div
        className="h-6 bg-muted/80 flex items-center justify-center cursor-grab active:cursor-grabbing border-b border-border"
        onPointerDown={handleDragStart}
        style={{ touchAction: "none" }}
      >
        <GripHorizontal className="w-4 h-4 text-muted-foreground" />
      </div>
      <div className="h-[calc(100%-24px)]">
        <PaneContainer pane={fw.pane} />
      </div>
      <div
        className="absolute bottom-0 right-0 w-4 h-4 cursor-se-resize"
        onPointerDown={handleResizeStart}
        style={{ touchAction: "none" }}
      >
        <svg
          className="w-3 h-3 text-muted-foreground absolute bottom-0.5 right-0.5"
          viewBox="0 0 10 10"
        >
          <path
            d="M8 2L2 8M8 5L5 8M8 8L8 8"
            stroke="currentColor"
            strokeWidth="1.5"
            fill="none"
          />
        </svg>
      </div>
    </div>
  );
}
