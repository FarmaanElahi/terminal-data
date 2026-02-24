import { useMemo } from "react";

interface ScreenerStatusProps {
  filteredSymbols: number;
  totalSymbols: number;
  lastUpdate: number | null;
  isLoading: boolean;
}

export function ScreenerStatus({
  filteredSymbols,
  totalSymbols,
  lastUpdate,
  isLoading,
}: ScreenerStatusProps) {
  const timeAgo = useMemo(() => {
    if (!lastUpdate) return null;
    const seconds = Math.floor((Date.now() - lastUpdate) / 1000);
    if (seconds < 5) return "just now";
    if (seconds < 60) return `${seconds}s ago`;
    const minutes = Math.floor(seconds / 60);
    return `${minutes}m ago`;
  }, [lastUpdate, /* refresh */ Math.floor(Date.now() / 5000)]);

  return (
    <div className="relative bottom-0 bg-background/80 backdrop-blur-sm border border-border/50 rounded-sm px-2 py-0.5 text-xs font-mono text-muted-foreground z-20 pointer-events-none select-none max-w-fit flex items-center gap-2">
      {isLoading ? (
        <div className="flex items-center gap-1.5">
          <div className="w-1 h-1 rounded-full bg-primary animate-pulse" />
          <span>Syncing...</span>
        </div>
      ) : (
        <span>
          {filteredSymbols} / {totalSymbols}
        </span>
      )}
      {timeAgo && !isLoading && <span className="opacity-40">{timeAgo}</span>}
    </div>
  );
}
