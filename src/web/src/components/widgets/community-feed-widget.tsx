import { useWidget } from "@/hooks/use-widget";
import type { WidgetProps } from "@/types/layout";
import { MessageSquare } from "lucide-react";

export function CommunityFeedWidget({
  instanceId,
  settings,
  onSettingsChange,
}: WidgetProps) {
  const s = (settings ?? {}) as Record<string, unknown>;
  const { useChannelEvent } = useWidget(instanceId);

  useChannelEvent((event) => {
    if (event.type === "context_change") {
      const payload = event.payload as { symbol?: string };
      if (payload.symbol) {
        onSettingsChange({ symbol: payload.symbol });
      }
    }
  });

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-2 p-2 border-b border-border shrink-0">
        <span className="text-xs font-medium text-foreground">
          Community {s.symbol ? `· ${s.symbol}` : ""}
        </span>
      </div>
      <div className="flex-1 flex flex-col items-center justify-center text-muted-foreground gap-3">
        <MessageSquare className="w-12 h-12" />
        <span className="text-sm">
          {s.symbol
            ? `Feed for ${s.symbol}`
            : "Select a symbol or link to a watchlist"}
        </span>
        <span className="text-xs text-muted-foreground/60">
          Community feed coming soon
        </span>
      </div>
    </div>
  );
}
