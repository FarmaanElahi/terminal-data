import React, {
  useState,
  useRef,
  useEffect,
  useCallback,
  useMemo,
} from "react";
import { Settings, ChevronRight, ChevronDown, List as ListIcon, ZoomIn, ZoomOut, Maximize2, Crop } from "lucide-react";
import { useWidget } from "@/hooks/use-widget";
import { useScreener } from "@/hooks/use-screener";
import { useListsQuery } from "@/queries/use-lists";
import type { WidgetProps } from "@/types/layout";
import type { ColumnDef } from "@/types/models";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";

import { Button } from "@/components/ui/button";
import { ColumnPropertiesDialog } from "./column-properties-dialog";
import { ListSelectionDialog } from "./list-selection-dialog";

// ─── Types ────────────────────────────────────────────────────────────────────

interface BubbleChartSettings {
  listId: string | null;
  xColumn: ColumnDef;
  yColumn: ColumnDef;
  sizeColumn: ColumnDef;
}

interface TooltipData {
  ticker: string;
  xVal: number;
  yVal: number;
  sizeVal: number;
  xLabel: string;
  yLabel: string;
  sizeLabel: string;
  cx: number;
  cy: number;
}

interface Viewport {
  xMin: number;
  xMax: number;
  yMin: number;
  yMax: number;
}

interface SelectBox {
  x1: number; y1: number;
  x2: number; y2: number;
}

// ─── Constants ────────────────────────────────────────────────────────────────

const MIN_R = 4;
const MAX_R = 22;
const MARGIN = { top: 20, right: 20, bottom: 48, left: 58 };
const ZOOM_FACTOR = 0.9; // 10% per button click
const LERP_SPEED = 0.16; // fraction of remaining distance covered per frame

// ─── Axis roles ───────────────────────────────────────────────────────────────

const AXIS_ROLES: {
  key: "xColumn" | "yColumn" | "sizeColumn";
  label: string;
  badge: string;
}[] = [
  { key: "xColumn",    label: "X Axis",       badge: "X" },
  { key: "yColumn",    label: "Y Axis",        badge: "Y" },
  { key: "sizeColumn", label: "Size (radius)", badge: "S" },
];

// ─── Helpers ─────────────────────────────────────────────────────────────────

function formatTick(v: number): string {
  const abs = Math.abs(v);
  if (abs >= 1e7) return `${(v / 1e7).toFixed(1)}Cr`;
  if (abs >= 1e5) return `${(v / 1e5).toFixed(1)}L`;
  if (abs >= 1e3) return `${(v / 1e3).toFixed(1)}K`;
  return parseFloat(v.toFixed(2)).toString();
}

function linearScale(
  domain: [number, number],
  range: [number, number],
): (v: number) => number {
  const [d0, d1] = domain;
  const [r0, r1] = range;
  if (d1 === d0) return () => (r0 + r1) / 2;
  return (v) => r0 + ((v - d0) / (d1 - d0)) * (r1 - r0);
}


function niceTicks(min: number, max: number, count = 5): number[] {
  if (min === max) return [min];
  const step = (max - min) / (count - 1);
  const ticks: number[] = [];
  for (let i = 0; i < count; i++) ticks.push(min + step * i);
  return ticks;
}

function bubbleColor(xVal: number | null): string {
  if (xVal === null || isNaN(xVal)) return "hsl(220 20% 55%)";
  if (xVal > 0) return "hsl(142 70% 50%)";
  if (xVal < 0) return "hsl(0 70% 55%)";
  return "hsl(220 20% 55%)";
}

/** "NSE:RELIANCE" → "RELIANCE" */
function shortTicker(t: string): string {
  const idx = t.lastIndexOf(":");
  return idx >= 0 ? t.slice(idx + 1) : t;
}

// ─── BubbleChartCanvas ────────────────────────────────────────────────────────

interface BubbleChartCanvasProps {
  tickers: string[];
  xValues: (number | null)[];
  yValues: (number | null)[];
  sizeValues: (number | null)[];
  xLabel: string;
  yLabel: string;
  sizeLabel: string;
  activeSymbol: string | null;
  onBubbleClick: (ticker: string) => void;
}

function BubbleChartCanvas({
  tickers,
  xValues,
  yValues,
  sizeValues,
  xLabel,
  yLabel,
  sizeLabel,
  activeSymbol,
  onBubbleClick,
}: BubbleChartCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [dims, setDims] = useState({ width: 600, height: 400 });
  const [tooltip, setTooltip] = useState<TooltipData | null>(null);
  const [viewport, setViewport] = useState<Viewport | null>(null);
  const [zoomMode, setZoomMode] = useState<"pan" | "select">("pan");
  const [selectBox, setSelectBox] = useState<SelectBox | null>(null);
  const isPanningRef = useRef(false);
  const panStartRef = useRef<{ px: number; py: number; vp: Viewport } | null>(null);
  const isSelectingRef = useRef(false);
  const selectStartRef = useRef<{ x: number; y: number } | null>(null);
  const userInteractedRef = useRef(false);

  // Animation refs — avoids stale closures in the RAF loop
  const vpRef = useRef<Viewport | null>(null);        // current rendered viewport
  const targetVpRef = useRef<Viewport | null>(null);  // zoom target
  const rafRef = useRef<number>(0);

  // Observe container size
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const obs = new ResizeObserver((entries) => {
      const { width, height } = entries[0].contentRect;
      if (width > 0 && height > 0) setDims({ width, height });
    });
    obs.observe(el);
    return () => obs.disconnect();
  }, []);

  // Valid data points
  const points = useMemo(() => {
    return tickers
      .map((ticker, i) => ({
        ticker,
        xv: xValues[i],
        yv: yValues[i],
        sv: sizeValues[i],
      }))
      .filter(
        (p) => p.xv !== null && p.yv !== null && !isNaN(p.xv!) && !isNaN(p.yv!),
      ) as { ticker: string; xv: number; yv: number; sv: number | null }[];
  }, [tickers, xValues, yValues, sizeValues]);

  // Base domain derived from data
  const baseDomain = useMemo((): Viewport | null => {
    if (points.length === 0) return null;
    const xs = points.map((p) => p.xv);
    const ys = points.map((p) => p.yv);
    const xMin = Math.min(...xs);
    const xMax = Math.max(...xs);
    const yMin = Math.min(...ys);
    const yMax = Math.max(...ys);
    const xPad = (xMax - xMin) * 0.12 || 1;
    const yPad = (yMax - yMin) * 0.12 || 1;
    return { xMin: xMin - xPad, xMax: xMax + xPad, yMin: yMin - yPad, yMax: yMax + yPad };
  }, [points]);

  // Keep user zoom/pan across data updates; only follow data if no interaction yet.
  useEffect(() => {
    if (!baseDomain) {
      if (!vpRef.current) setViewport(null);
      return;
    }

    const hasUserInteracted = userInteractedRef.current;

    if (!vpRef.current || !viewport || !hasUserInteracted) {
      setViewport(baseDomain);
      vpRef.current = baseDomain;
      targetVpRef.current = null;
    }
  }, [baseDomain, viewport]);

  // Keep vpRef in sync with rendered viewport
  useEffect(() => { vpRef.current = viewport; }, [viewport]);

  // Cancel RAF on unmount
  useEffect(() => () => cancelAnimationFrame(rafRef.current), []);

  // Smooth animate viewport toward targetVpRef
  const animateTo = useCallback((target: Viewport) => {
    targetVpRef.current = target;
    cancelAnimationFrame(rafRef.current);

    const tick = () => {
      const cur = vpRef.current;
      const tgt = targetVpRef.current;
      if (!cur || !tgt) return;

      const next: Viewport = {
        xMin: cur.xMin + (tgt.xMin - cur.xMin) * LERP_SPEED,
        xMax: cur.xMax + (tgt.xMax - cur.xMax) * LERP_SPEED,
        yMin: cur.yMin + (tgt.yMin - cur.yMin) * LERP_SPEED,
        yMax: cur.yMax + (tgt.yMax - cur.yMax) * LERP_SPEED,
      };
      vpRef.current = next;
      setViewport(next);

      const eps = 1e-5;
      const done =
        Math.abs(next.xMin - tgt.xMin) < eps &&
        Math.abs(next.xMax - tgt.xMax) < eps &&
        Math.abs(next.yMin - tgt.yMin) < eps &&
        Math.abs(next.yMax - tgt.yMax) < eps;

      if (done) {
        vpRef.current = tgt;
        setViewport(tgt);
        targetVpRef.current = null;
      } else {
        rafRef.current = requestAnimationFrame(tick);
      }
    };

    rafRef.current = requestAnimationFrame(tick);
  }, []);

  const vp = viewport ?? baseDomain ?? { xMin: -1, xMax: 1, yMin: -1, yMax: 1 };

  const chartW = dims.width - MARGIN.left - MARGIN.right;
  const chartH = dims.height - MARGIN.top - MARGIN.bottom;

  const xScale = useMemo(
    () => linearScale([vp.xMin, vp.xMax], [0, chartW]),
    [vp.xMin, vp.xMax, chartW],
  );
  const yScale = useMemo(
    () => linearScale([vp.yMin, vp.yMax], [chartH, 0]),
    [vp.yMin, vp.yMax, chartH],
  );
  // Size scale (not affected by zoom — bubble radius in px stays constant)
  const sizeScale = useMemo(() => {
    const ss = points.map((p) => p.sv).filter((v) => v !== null) as number[];
    const sMin = ss.length ? Math.min(...ss) : 0;
    const sMax = ss.length ? Math.max(...ss) : 1;
    return (v: number | null): number => {
      if (v === null || isNaN(v) || sMax === sMin) return MIN_R;
      return MIN_R + (MAX_R - MIN_R) * Math.sqrt(Math.max(0, (v - sMin) / (sMax - sMin)));
    };
  }, [points]);

  const xTicks = useMemo(() => niceTicks(vp.xMin, vp.xMax), [vp.xMin, vp.xMax]);
  const yTicks = useMemo(() => niceTicks(vp.yMin, vp.yMax), [vp.yMin, vp.yMax]);

  const zeroX = vp.xMin <= 0 && vp.xMax >= 0 ? xScale(0) : null;
  const zeroY = vp.yMin <= 0 && vp.yMax >= 0 ? yScale(0) : null;

  // ─── Zoom helpers ──────────────────────────────────────────────────

  /** Compute the next viewport given a pivot in chart-pixel space and a scale factor,
   *  always reading from vpRef so it's never stale during animation. */
  const zoomAround = useCallback(
    (pivotPx: number, pivotPy: number, factor: number) => {
      const v = vpRef.current ?? baseDomain;
      if (!v) return;
      const xRange = v.xMax - v.xMin;
      const yRange = v.yMax - v.yMin;
      // Convert pivot from chart-pixels to data space
      const pivotX = v.xMin + (pivotPx / chartW) * xRange;
      const pivotY = v.yMax - (pivotPy / chartH) * yRange; // y-axis is flipped
      animateTo({
        xMin: pivotX + (v.xMin - pivotX) * factor,
        xMax: pivotX + (v.xMax - pivotX) * factor,
        yMin: pivotY + (v.yMin - pivotY) * factor,
        yMax: pivotY + (v.yMax - pivotY) * factor,
      });
    },
    [animateTo, baseDomain, chartW, chartH],
  );

  const zoomIn = useCallback(() => {
    userInteractedRef.current = true;
    zoomAround(chartW / 2, chartH / 2, ZOOM_FACTOR);
  }, [zoomAround, chartW, chartH]);

  const zoomOut = useCallback(() => {
    userInteractedRef.current = true;
    zoomAround(chartW / 2, chartH / 2, 1 / ZOOM_FACTOR);
  }, [zoomAround, chartW, chartH]);

  const resetZoom = useCallback(() => {
    if (baseDomain) {
      userInteractedRef.current = false;
      animateTo(baseDomain);
    }
  }, [animateTo, baseDomain]);

  // Wheel to zoom — proportional to deltaY so trackpad feels smooth
  const handleWheel = useCallback(
    (e: React.WheelEvent<SVGSVGElement>) => {
      e.preventDefault();
      userInteractedRef.current = true;
      const rect = (e.currentTarget as SVGSVGElement).getBoundingClientRect();
      const px = e.clientX - rect.left - MARGIN.left;
      const py = e.clientY - rect.top - MARGIN.top;

      // Normalise delta across wheel modes; clamp to avoid single-event jumps
      let delta = e.deltaY;
      if (e.deltaMode === 1) delta *= 15;  // line → px
      if (e.deltaMode === 2) delta *= 300; // page → px
      delta = Math.max(-150, Math.min(150, delta));

      // factor > 1 = zoom out (expand domain), factor < 1 = zoom in (shrink domain)
      const factor = Math.exp(delta * 0.006);
      zoomAround(px, py, factor);
    },
    [zoomAround],
  );

  // ─── Pan / Box-select mouse handlers ──────────────────────────────

  const handleMouseDown = useCallback(
    (e: React.MouseEvent<SVGSVGElement>) => {
      if (e.button !== 0) return;
      const rect = (e.currentTarget as SVGSVGElement).getBoundingClientRect();
      const px = e.clientX - rect.left - MARGIN.left;
      const py = e.clientY - rect.top - MARGIN.top;
      // Only start a selection when the click is inside the chart area
      const inChart = px >= 0 && px <= chartW && py >= 0 && py <= chartH;

      if (zoomMode === "select" && inChart) {
        isSelectingRef.current = true;
        selectStartRef.current = { x: px, y: py };
        setSelectBox({ x1: px, y1: py, x2: px, y2: py });
      } else {
        userInteractedRef.current = true;
        isPanningRef.current = true;
        panStartRef.current = { px: e.clientX, py: e.clientY, vp: { ...vp } };
      }
    },
    [zoomMode, chartW, chartH, vp],
  );

  const handleMouseMoveOnSvg = useCallback(
    (e: React.MouseEvent<SVGSVGElement>) => {
      if (isSelectingRef.current && selectStartRef.current) {
        const rect = (e.currentTarget as SVGSVGElement).getBoundingClientRect();
        const px = Math.max(0, Math.min(chartW, e.clientX - rect.left - MARGIN.left));
        const py = Math.max(0, Math.min(chartH, e.clientY - rect.top - MARGIN.top));
        setSelectBox({ x1: selectStartRef.current.x, y1: selectStartRef.current.y, x2: px, y2: py });
        return;
      }
      if (!isPanningRef.current || !panStartRef.current) return;
      const dx = e.clientX - panStartRef.current.px;
      const dy = e.clientY - panStartRef.current.py;
      const { vp: startVp } = panStartRef.current;
      const xRange = startVp.xMax - startVp.xMin;
      const yRange = startVp.yMax - startVp.yMin;
      const next = {
        xMin: startVp.xMin - (dx / chartW) * xRange,
        xMax: startVp.xMax - (dx / chartW) * xRange,
        yMin: startVp.yMin + (dy / chartH) * yRange,
        yMax: startVp.yMax + (dy / chartH) * yRange,
      };
      cancelAnimationFrame(rafRef.current);
      targetVpRef.current = null;
      vpRef.current = next;
      setViewport(next);
    },
    [chartW, chartH],
  );

  const handleMouseUp = useCallback(() => {
    if (isSelectingRef.current) {
      isSelectingRef.current = false;
      selectStartRef.current = null;
      setSelectBox((box) => {
        if (!box) return null;
        const minX = Math.min(box.x1, box.x2);
        const maxX = Math.max(box.x1, box.x2);
        const minY = Math.min(box.y1, box.y2);
        const maxY = Math.max(box.y1, box.y2);
        // Ignore tiny drag (misclick)
        if (maxX - minX > 8 && maxY - minY > 8) {
          const v = vpRef.current;
          if (v) {
            userInteractedRef.current = true;
            const xRange = v.xMax - v.xMin;
            const yRange = v.yMax - v.yMin;
            // Note: y-axis is flipped — top of chart = yMax in data space
            animateTo({
              xMin: v.xMin + (minX / chartW) * xRange,
              xMax: v.xMin + (maxX / chartW) * xRange,
              yMin: v.yMax - (maxY / chartH) * yRange,
              yMax: v.yMax - (minY / chartH) * yRange,
            });
          }
        }
        return null;
      });
      return;
    }
    isPanningRef.current = false;
    panStartRef.current = null;
  }, [animateTo, chartW, chartH]);

  // Tooltip on bubble hover
  const handleBubbleMouseMove = useCallback(
    (e: React.MouseEvent<SVGCircleElement>, p: (typeof points)[0]) => {
      e.stopPropagation();
      const rect = (e.currentTarget.ownerSVGElement as SVGSVGElement).getBoundingClientRect();
      setTooltip({
        ticker: p.ticker,
        xVal: p.xv,
        yVal: p.yv,
        sizeVal: p.sv ?? 0,
        xLabel,
        yLabel,
        sizeLabel,
        cx: e.clientX - rect.left,
        cy: e.clientY - rect.top,
      });
    },
    [xLabel, yLabel, sizeLabel],
  );

  const clipId = `bubble-clip-${Math.abs(dims.width | 0)}`;

  return (
    <div ref={containerRef} className="relative size-full">
      <svg
        width={dims.width}
        height={dims.height}
        style={{
          overflow: "visible",
          cursor: zoomMode === "select"
            ? (isSelectingRef.current ? "crosshair" : "crosshair")
            : (isPanningRef.current ? "grabbing" : "grab"),
        }}
        onWheel={handleWheel}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMoveOnSvg}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
      >
        <defs>
          <clipPath id={clipId}>
            <rect x={0} y={0} width={chartW} height={chartH} />
          </clipPath>
        </defs>

        <g transform={`translate(${MARGIN.left},${MARGIN.top})`}>
          {/* Y tick labels (static, outside clip) */}
          {yTicks.map((t, i) => (
            <text key={i} x={-6} y={yScale(t)} textAnchor="end"
              dominantBaseline="middle" fontSize={10} fill="currentColor" opacity={0.5}>
              {formatTick(t)}
            </text>
          ))}

          {/* X tick labels */}
          {xTicks.map((t, i) => (
            <text key={i} x={xScale(t)} y={chartH + 16} textAnchor="middle"
              fontSize={10} fill="currentColor" opacity={0.5}>
              {formatTick(t)}
            </text>
          ))}

          {/* Axis labels */}
          <text x={chartW / 2} y={chartH + 36} textAnchor="middle"
            fontSize={11} fill="currentColor" opacity={0.6}>
            {xLabel}
          </text>
          <text x={-chartH / 2} y={-44} textAnchor="middle"
            fontSize={11} fill="currentColor" opacity={0.6}
            transform="rotate(-90)">
            {yLabel}
          </text>

          {/* Clipped data area */}
          <g clipPath={`url(#${clipId})`}>
            {/* Grid */}
            {yTicks.map((t, i) => (
              <line key={i} x1={0} x2={chartW} y1={yScale(t)} y2={yScale(t)}
                stroke="currentColor" strokeOpacity={0.08} strokeDasharray="4 4" />
            ))}
            {xTicks.map((t, i) => (
              <line key={i} x1={xScale(t)} x2={xScale(t)} y1={0} y2={chartH}
                stroke="currentColor" strokeOpacity={0.08} strokeDasharray="4 4" />
            ))}

            {/* Zero crosshairs */}
            {zeroY !== null && (
              <line x1={0} x2={chartW} y1={zeroY} y2={zeroY}
                stroke="currentColor" strokeOpacity={0.2} />
            )}
            {zeroX !== null && (
              <line x1={zeroX} x2={zeroX} y1={0} y2={chartH}
                stroke="currentColor" strokeOpacity={0.2} />
            )}

            {/* Bubbles */}
            {points.map((p) => {
              const cx = xScale(p.xv);
              const cy = yScale(p.yv);
              const r = sizeScale(p.sv);
              const color = bubbleColor(p.xv);
              const isActive = p.ticker === activeSymbol;
              const label = shortTicker(p.ticker);
              // Only show label if bubble is large enough to fit text
              const showLabel = r >= 10;
              const fontSize = Math.max(7, Math.min(10, r * 0.75));

              return (
                <g key={p.ticker}>
                  <circle
                    cx={cx} cy={cy} r={r}
                    fill={color}
                    fillOpacity={0.38}
                    stroke={isActive ? "white" : color}
                    strokeWidth={isActive ? 2 : 1}
                    strokeOpacity={isActive ? 1 : 0.7}
                    style={{ cursor: "pointer" }}
                    onMouseMove={(e) => handleBubbleMouseMove(e, p)}
                    onMouseLeave={() => setTooltip(null)}
                    onClick={(e) => { e.stopPropagation(); onBubbleClick(p.ticker); }}
                  />
                  {showLabel && (
                    <text
                      x={cx} y={cy}
                      textAnchor="middle"
                      dominantBaseline="middle"
                      fontSize={fontSize}
                      fill="white"
                      opacity={0.9}
                      style={{ pointerEvents: "none", userSelect: "none" }}
                    >
                      {label}
                    </text>
                  )}
                  {/* Always show label outside small bubbles */}
                  {!showLabel && (
                    <text
                      x={cx} y={cy - r - 3}
                      textAnchor="middle"
                      dominantBaseline="auto"
                      fontSize={8}
                      fill="currentColor"
                      opacity={0.6}
                      style={{ pointerEvents: "none", userSelect: "none" }}
                    >
                      {label}
                    </text>
                  )}
                </g>
              );
            })}

            {/* Box-select overlay */}
            {selectBox && (
              <rect
                x={Math.min(selectBox.x1, selectBox.x2)}
                y={Math.min(selectBox.y1, selectBox.y2)}
                width={Math.abs(selectBox.x2 - selectBox.x1)}
                height={Math.abs(selectBox.y2 - selectBox.y1)}
                fill="hsl(210 100% 70%)"
                fillOpacity={0.08}
                stroke="hsl(210 100% 70%)"
                strokeWidth={1}
                strokeDasharray="5 3"
                strokeOpacity={0.7}
                style={{ pointerEvents: "none" }}
              />
            )}
          </g>

          {/* Chart border */}
          <rect x={0} y={0} width={chartW} height={chartH}
            fill="none" stroke="currentColor" strokeOpacity={0.12} />
        </g>
      </svg>

      {/* Zoom controls */}
      <div className="absolute bottom-12 right-3 flex flex-col gap-1">
        <button
          className={`flex h-6 w-6 items-center justify-center rounded border backdrop-blur-sm transition-colors ${
            zoomMode === "select"
              ? "border-blue-500/60 bg-blue-500/20 text-blue-400"
              : "border-border bg-background/80 text-muted-foreground hover:bg-accent hover:text-foreground"
          }`}
          onClick={() => setZoomMode((m) => (m === "select" ? "pan" : "select"))}
          title={zoomMode === "select" ? "Box zoom active — click to switch to pan" : "Box zoom (drag to select area)"}
        >
          <Crop className="size-3" />
        </button>
        <button
          className="flex h-6 w-6 items-center justify-center rounded border border-border bg-background/80 text-muted-foreground hover:bg-accent hover:text-foreground backdrop-blur-sm"
          onClick={zoomIn}
          title="Zoom in"
        >
          <ZoomIn className="size-3" />
        </button>
        <button
          className="flex h-6 w-6 items-center justify-center rounded border border-border bg-background/80 text-muted-foreground hover:bg-accent hover:text-foreground backdrop-blur-sm"
          onClick={zoomOut}
          title="Zoom out"
        >
          <ZoomOut className="size-3" />
        </button>
        <button
          className="flex h-6 w-6 items-center justify-center rounded border border-border bg-background/80 text-muted-foreground hover:bg-accent hover:text-foreground backdrop-blur-sm"
          onClick={resetZoom}
          title="Reset zoom"
        >
          <Maximize2 className="size-3" />
        </button>
      </div>

      {/* Tooltip */}
      {tooltip && (
        <div
          className="pointer-events-none absolute z-10 rounded border border-border bg-popover px-2.5 py-2 text-xs shadow-lg"
          style={{
            left: tooltip.cx + 12,
            top: tooltip.cy - 10,
            transform: tooltip.cx > dims.width * 0.7 ? "translateX(-110%)" : undefined,
          }}
        >
          <p className="mb-1 font-semibold text-foreground">{tooltip.ticker}</p>
          <p className="text-muted-foreground">
            {tooltip.xLabel}:{" "}
            <span className="text-foreground">{tooltip.xVal.toFixed(2)}</span>
          </p>
          <p className="text-muted-foreground">
            {tooltip.yLabel}:{" "}
            <span className="text-foreground">{formatTick(tooltip.yVal)}</span>
          </p>
          <p className="text-muted-foreground">
            {tooltip.sizeLabel}:{" "}
            <span className="text-foreground">{tooltip.sizeVal.toFixed(2)}</span>
          </p>
        </div>
      )}
    </div>
  );
}

// ─── BubbleChartSettingsDialog ────────────────────────────────────────────────

interface SettingsDialogProps {
  open: boolean;
  onClose: () => void;
  settings: BubbleChartSettings;
  onApply: (s: BubbleChartSettings) => void;
}

function BubbleChartSettingsDialog({
  open,
  onClose,
  settings,
  onApply,
}: SettingsDialogProps) {
  const [draft, setDraft] = useState<BubbleChartSettings>(settings);
  const [editingRole, setEditingRole] = useState<
    "xColumn" | "yColumn" | "sizeColumn" | null
  >(null);

  useEffect(() => {
    if (open) {
      setDraft(settings);
      setEditingRole(null);
    }
  }, [open, settings]);

  const editingColumn = editingRole ? draft[editingRole] : null;

  const handleSaveColumn = (updated: ColumnDef) => {
    if (!editingRole) return;
    setDraft((d) => ({ ...d, [editingRole]: updated }));
    setEditingRole(null);
  };

  const handleApply = () => {
    onApply(draft);
    onClose();
  };

  return (
    <>
      <Dialog open={open} onOpenChange={(io) => { if (!io) onClose(); }}>
        <DialogContent
          showCloseButton={false}
          className="sm:max-w-lg p-0 gap-0 overflow-hidden flex flex-col max-h-[85vh]"
        >
          {/* Header */}
          <DialogHeader className="px-5 py-3.5 border-b border-border shrink-0">
            <div className="flex items-center justify-between">
              <div>
                <DialogTitle className="text-sm font-semibold">
                  Bubble Chart Settings
                </DialogTitle>
                <DialogDescription className="text-xs mt-0.5">
                  Configure list and axis formulas
                </DialogDescription>
              </div>
              <button
                onClick={onClose}
                className="text-muted-foreground hover:text-foreground p-1 rounded-sm hover:bg-muted transition-colors"
              >
                <span className="text-sm leading-none">✕</span>
              </button>
            </div>
          </DialogHeader>

          {/* Body */}
          <div className="flex-1 overflow-auto bg-card/50">
            {/* Column list header */}
            <div className="grid grid-cols-[36px_1fr_60px_32px] items-center px-3 py-2 border-b border-border bg-muted/30 text-xs uppercase tracking-wider text-muted-foreground font-semibold shrink-0">
              <div className="text-center">Axis</div>
              <div>Column Name / Formula</div>
              <div className="text-center">Type</div>
              <div />
            </div>

            {/* Axis rows */}
            {AXIS_ROLES.map(({ key, badge }) => {
              const col = draft[key];
              return (
                <div
                  key={key}
                  className="grid grid-cols-[36px_1fr_60px_32px] items-center px-3 border-b border-border/50 group hover:bg-muted/30 transition-all cursor-pointer"
                  style={{ minHeight: "44px" }}
                  onClick={() => setEditingRole(key)}
                >
                  <div className="flex justify-center">
                    <span className="text-xs font-bold text-muted-foreground/70">
                      {badge}
                    </span>
                  </div>

                  <div className="pr-2 flex flex-col justify-center overflow-hidden">
                    <div className="flex items-center gap-2">
                      <div
                        className="w-2 h-2 rounded-full shrink-0"
                        style={{
                          backgroundColor:
                            col.display_color || "var(--muted-foreground)",
                        }}
                      />
                      <span className="text-xs font-medium text-foreground truncate">
                        {col.name}
                      </span>
                      <ChevronRight className="w-3 h-3 text-muted-foreground/20 group-hover:text-muted-foreground/50 transition-colors" />
                    </div>
                    <span className="text-xs text-muted-foreground truncate font-mono">
                      {col.value_formula || "no formula"}
                    </span>
                  </div>

                  <div className="flex justify-center">
                    <span className="text-xs uppercase font-bold px-1.5 py-0.5 rounded-full text-blue-500 bg-blue-500/10 border border-blue-500/20">
                      VAL
                    </span>
                  </div>

                  <div />
                </div>
              );
            })}
          </div>

          {/* Footer */}
          <div className="flex items-center justify-end gap-2 px-4 py-3 border-t border-border bg-muted/20 shrink-0">
            <Button
              variant="ghost"
              size="sm"
              onClick={onClose}
              className="h-8 text-xs"
            >
              Cancel
            </Button>
            <Button
              size="sm"
              onClick={handleApply}
              className="h-8 text-xs font-semibold"
            >
              Apply
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Column properties — reuses the screener's exact dialog */}
      <ColumnPropertiesDialog
        open={editingRole !== null}
        onClose={() => setEditingRole(null)}
        column={editingColumn}
        onSave={handleSaveColumn}
      />
    </>
  );
}

// ─── BubbleChartWidget ────────────────────────────────────────────────────────

export function BubbleChartWidget({ instanceId }: WidgetProps) {
  const { settings, updateSettings, channelContext, setChannelSymbol } =
    useWidget<BubbleChartSettings>(instanceId);

  const { data: lists } = useListsQuery();
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [listDialogOpen, setListDialogOpen] = useState(false);

  const selectedList = useMemo(
    () => lists?.find((l) => l.id === settings.listId) ?? null,
    [lists, settings.listId],
  );

  const columns = useMemo(
    () => [settings.xColumn, settings.yColumn, settings.sizeColumn],
    [settings.xColumn, settings.yColumn, settings.sizeColumn],
  );

  const { tickers, values, isLoading } = useScreener(
    instanceId,
    settings.listId,
    settings.listId ? columns : null,
    false,
  );

  const tickerNames = useMemo(() => tickers.map((r) => r.ticker), [tickers]);

  const toNumArray = useCallback(
    (colId: string) =>
      (values[colId] ?? []).map((v) => (typeof v === "number" ? v : null)),
    [values],
  );

  const xValues = useMemo(
    () => toNumArray(settings.xColumn.id),
    [toNumArray, settings.xColumn.id],
  );
  const yValues = useMemo(
    () => toNumArray(settings.yColumn.id),
    [toNumArray, settings.yColumn.id],
  );
  const sizeValues = useMemo(
    () => toNumArray(settings.sizeColumn.id),
    [toNumArray, settings.sizeColumn.id],
  );

  const handleApply = useCallback(
    (s: BubbleChartSettings) => {
      updateSettings(s as unknown as Record<string, unknown>);
    },
    [updateSettings],
  );

  const hasData = !isLoading && tickerNames.length > 0;

  return (
    <div className="flex size-full flex-col overflow-hidden bg-background text-foreground">
      {/* ─── Header — mirrors screener toolbar ──────────────────── */}
      <div className="flex items-center gap-2 p-2 border-b border-border shrink-0">
        <Button
          variant="outline"
          size="sm"
          className="h-7 gap-2 px-2.5 bg-background/50 hover:bg-background/80 border-border/50 text-xs font-medium"
          onClick={() => setListDialogOpen(true)}
        >
          <ListIcon className="w-3.5 h-3.5 text-primary" />
          <span className="truncate max-w-[120px]">
            {selectedList?.name ?? "Select List"}
          </span>
          <ChevronDown className="w-3.5 h-3.5 text-muted-foreground" />
        </Button>

        <ListSelectionDialog
          open={listDialogOpen}
          onOpenChange={setListDialogOpen}
          selectedId={settings.listId}
          onSelect={(id) => updateSettings({ listId: id })}
        />

        <div className="flex-1" />

        <button
          onClick={() => setSettingsOpen(true)}
          className="p-1 rounded-sm text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
          title="Edit columns"
        >
          <Settings className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* ─── Chart area ─────────────────────────────────────────── */}
      <div className="relative flex-1 min-h-0">
        {!settings.listId ? (
          <div className="flex size-full flex-col items-center justify-center gap-2 text-muted-foreground">
            <p className="text-sm">No list selected</p>
            <Button variant="outline" size="sm" onClick={() => setListDialogOpen(true)}>
              Select List
            </Button>
          </div>
        ) : isLoading ? (
          <div className="flex size-full items-center justify-center text-sm text-muted-foreground">
            Loading…
          </div>
        ) : !hasData ? (
          <div className="flex size-full items-center justify-center text-sm text-muted-foreground">
            No data
          </div>
        ) : (
          <BubbleChartCanvas
            tickers={tickerNames}
            xValues={xValues}
            yValues={yValues}
            sizeValues={sizeValues}
            xLabel={settings.xColumn.name}
            yLabel={settings.yColumn.name}
            sizeLabel={settings.sizeColumn.name}
            activeSymbol={channelContext?.symbol ?? null}
            onBubbleClick={setChannelSymbol}
          />
        )}
      </div>

      <BubbleChartSettingsDialog
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        settings={settings}
        onApply={handleApply}
      />
    </div>
  );
}
