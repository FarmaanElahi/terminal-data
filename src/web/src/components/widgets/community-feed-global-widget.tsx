import { useState } from "react";
import { useWidget } from "@/hooks/use-widget";
import type { WidgetProps } from "@/types/layout";
import { useCommunityGlobalFeed } from "@/queries/use-community-feed";
import type { StockTwitsMessage } from "@/types/models";
import { TrendingUp, TrendingDown } from "lucide-react";
import { cn } from "@/lib/utils";

// ─── Symbol conversion ────────────────────────────────────────────────
// StockTwits body uses TICKER.EXCHANGE; we use EXCHANGE:TICKER.
// Only NSE/BSE get an exchange prefix — all others are returned bare.

function stToTvSymbol(stSymbol: string): string {
  const parts = stSymbol.split(".");
  if (parts.length === 2) {
    const [ticker, exchange] = parts;
    if (exchange === "NSE" || exchange === "BSE") {
      return `${exchange}:${ticker}`;
    }
  }
  return stSymbol;
}

// ─── Body renderer ────────────────────────────────────────────────────
// Splits on $CASHTAG patterns and renders them as clickable spans.

function renderBody(
  body: string,
  onSymbolClick: (symbol: string) => void,
): React.ReactNode {
  const parts = body.split(/(\$[A-Z][A-Z0-9]*(?:\.[A-Z]+)?)/g);
  return parts.map((part, i) => {
    if (part.startsWith("$")) {
      const tvSymbol = stToTvSymbol(part.slice(1));
      return (
        <span
          key={i}
          className="text-primary cursor-pointer hover:underline font-medium"
          onClick={(e) => {
            e.stopPropagation();
            onSymbolClick(tvSymbol);
          }}
        >
          {part}
        </span>
      );
    }
    return part;
  });
}

// ─── Helpers ──────────────────────────────────────────────────────────

function timeAgo(dateStr: string): string {
  const diff = (Date.now() - new Date(dateStr).getTime()) / 1000;
  if (diff < 60) return `${Math.floor(diff)}s`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h`;
  return `${Math.floor(diff / 86400)}d`;
}

// ─── Avatar ───────────────────────────────────────────────────────────
// Falls back to an initial-based placeholder if the image fails to load.

function Avatar({ src, username }: { src?: string; username: string }) {
  const [failed, setFailed] = useState(false);

  if (src && !failed) {
    return (
      <img
        src={src}
        alt=""
        className="w-7 h-7 rounded-full shrink-0 bg-muted object-cover"
        onError={() => setFailed(true)}
      />
    );
  }

  return (
    <div className="w-7 h-7 rounded-full bg-primary/20 flex items-center justify-center text-[10px] text-primary shrink-0 font-bold">
      {username.slice(0, 1).toUpperCase()}
    </div>
  );
}

// ─── Feed type options ────────────────────────────────────────────────

const FEED_OPTIONS = [
  { value: "trending", label: "Trending" },
  { value: "suggested", label: "Suggested" },
  { value: "popular", label: "Popular" },
];

// ─── Post Card ────────────────────────────────────────────────────────

function PostCard({
  msg,
  onSymbolClick,
}: {
  msg: StockTwitsMessage;
  onSymbolClick: (symbol: string) => void;
}) {
  const sentiment = msg.entities?.sentiment?.basic;
  const likes = msg.likes?.total ?? 0;
  const symbols = msg.symbols ?? [];

  return (
    <div className="px-3 py-2.5 border-b border-border/50 hover:bg-muted/20 transition-colors">
      <div className="flex items-start gap-2">
        <Avatar src={msg.user.avatar_url_ssl} username={msg.user.username} />

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className="text-[11px] font-semibold text-foreground">
              {msg.user.username}
            </span>
            <span className="text-[10px] text-muted-foreground">
              {timeAgo(msg.created_at)}
            </span>
            {sentiment && (
              <span
                className={cn(
                  "text-[9px] font-bold px-1 py-0.5 rounded uppercase tracking-wide",
                  sentiment === "Bullish"
                    ? "bg-emerald-500/15 text-emerald-500"
                    : "bg-red-500/15 text-red-500",
                )}
              >
                {sentiment === "Bullish" ? (
                  <TrendingUp className="w-2.5 h-2.5 inline mr-0.5" />
                ) : (
                  <TrendingDown className="w-2.5 h-2.5 inline mr-0.5" />
                )}
                {sentiment}
              </span>
            )}
          </div>
          <p className="text-[11px] text-foreground/80 mt-0.5 leading-relaxed line-clamp-4">
            {renderBody(msg.body, onSymbolClick)}
          </p>
          {(symbols.length > 0 || likes > 0) && (
            <div className="flex items-center gap-2 mt-1 flex-wrap">
              {symbols.map((s) => {
                const tvSymbol = stToTvSymbol(s.symbol);
                return (
                  <button
                    key={s.symbol}
                    onClick={() => onSymbolClick(tvSymbol)}
                    className="text-[9px] font-mono bg-muted/60 text-primary px-1 py-0.5 rounded hover:bg-primary/15 transition-colors"
                    title={s.title}
                  >
                    {tvSymbol}
                  </button>
                );
              })}
              {likes > 0 && (
                <span className="text-[10px] text-muted-foreground">
                  ♥ {likes}
                </span>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function PostSkeleton() {
  return (
    <div className="px-3 py-2.5 border-b border-border/50 animate-pulse">
      <div className="flex items-start gap-2">
        <div className="w-7 h-7 rounded-full bg-muted shrink-0" />
        <div className="flex-1 space-y-1.5">
          <div className="h-2.5 bg-muted rounded w-24" />
          <div className="h-2 bg-muted rounded w-full" />
          <div className="h-2 bg-muted rounded w-3/4" />
        </div>
      </div>
    </div>
  );
}

// ─── Widget ───────────────────────────────────────────────────────────

export function CommunityFeedGlobalWidget({
  instanceId,
  settings,
  onSettingsChange,
}: WidgetProps) {
  const s = (settings ?? {}) as Record<string, unknown>;
  const { setChannelSymbol } = useWidget(instanceId);
  const [feed, setFeed] = useState<string>((s.feed as string) ?? "trending");

  const { data, isLoading, isError } = useCommunityGlobalFeed(feed, 20);
  const messages = data?.messages ?? data?.data ?? [];

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center gap-2 px-3 py-2 border-b border-border shrink-0">
        <span className="text-xs font-medium text-foreground flex-1">
          Community Feed
        </span>
        <div className="flex items-center gap-0.5">
          {FEED_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => {
                setFeed(opt.value);
                onSettingsChange({ feed: opt.value });
              }}
              className={cn(
                "px-2 py-0.5 text-[10px] rounded-sm transition-colors",
                feed === opt.value
                  ? "bg-primary/15 text-primary"
                  : "text-muted-foreground hover:text-foreground hover:bg-muted",
              )}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto scrollbar-thin">
        {isLoading ? (
          <>
            <PostSkeleton />
            <PostSkeleton />
            <PostSkeleton />
          </>
        ) : isError ? (
          <div className="flex items-center justify-center h-full text-muted-foreground text-xs">
            Failed to load feed
          </div>
        ) : messages.length === 0 ? (
          <div className="flex items-center justify-center h-full text-muted-foreground text-xs">
            No posts found
          </div>
        ) : (
          messages.map((msg) => (
            <PostCard key={msg.id} msg={msg} onSymbolClick={setChannelSymbol} />
          ))
        )}
      </div>
    </div>
  );
}
