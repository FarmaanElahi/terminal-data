import { useMemo } from "react";

interface ScreenerStatusProps {
  totalSymbols: number;
  lastUpdate: number | null;
  isLoading: boolean;
}

export function ScreenerStatus({
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
    <div className="border-t border-border px-4 py-1 flex items-center gap-4 text-[11px] text-muted-foreground bg-card/30 shrink-0">
      <span>
        {isLoading ? (
          <span className="flex items-center gap-1">
            <svg className="animate-spin h-3 w-3" viewBox="0 0 24 24">
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
                fill="none"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"
              />
            </svg>
            Loading...
          </span>
        ) : (
          `${totalSymbols} symbols`
        )}
      </span>

      {timeAgo && (
        <>
          <span className="text-border">·</span>
          <span>Last update: {timeAgo}</span>
        </>
      )}
    </div>
  );
}
