import { useCallback } from "react";
import { Bell } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useNotificationsStore } from "@/stores/notifications-store";
import { cn } from "@/lib/utils";

export function NotificationBell() {
  const { notifications, browserPermission, markAllRead, clearAll, setBrowserPermission } =
    useNotificationsStore();

  const unread = notifications.filter((n) => !n.read).length;

  const handleRequestPermission = useCallback(async () => {
    if (!("Notification" in window)) return;
    const result = await Notification.requestPermission();
    setBrowserPermission(result);
  }, [setBrowserPermission]);

  return (
    <DropdownMenu onOpenChange={(open) => open && markAllRead()}>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          className="relative h-6 w-6"
          title="Notifications"
        >
          <Bell className="w-3.5 h-3.5" />
          {unread > 0 && (
            <span className="absolute -top-0.5 -right-0.5 flex h-3.5 w-3.5 items-center justify-center rounded-full bg-destructive text-[9px] font-bold text-destructive-foreground leading-none">
              {unread > 9 ? "9+" : unread}
            </span>
          )}
        </Button>
      </DropdownMenuTrigger>

      <DropdownMenuContent align="end" className="w-80 p-0">
        {/* Header */}
        <div className="flex items-center justify-between px-3 py-2 border-b">
          <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Notifications
          </span>
          {notifications.length > 0 && (
            <button
              onClick={(e) => {
                e.preventDefault();
                clearAll();
              }}
              className="text-[10px] text-muted-foreground hover:text-foreground transition-colors"
            >
              Clear all
            </button>
          )}
        </div>

        {/* Browser notification permission prompt */}
        {browserPermission === "default" && (
          <>
            <div className="px-3 py-2 bg-muted/40 border-b">
              <p className="text-[11px] text-muted-foreground mb-1.5">
                Enable system notifications to get alerts even when the app is in the background.
              </p>
              <button
                onClick={(e) => {
                  e.preventDefault();
                  handleRequestPermission();
                }}
                className="text-[11px] text-primary hover:underline font-medium"
              >
                Enable browser notifications
              </button>
            </div>
          </>
        )}

        {/* Notification list */}
        <div className="max-h-80 overflow-y-auto">
          {notifications.length === 0 ? (
            <div className="px-3 py-6 text-center">
              <p className="text-xs text-muted-foreground">No notifications yet</p>
            </div>
          ) : (
            notifications.map((n) => (
              <div
                key={n.id}
                className={cn(
                  "px-3 py-2.5 border-b last:border-0 transition-colors",
                  !n.read && "bg-primary/5",
                )}
              >
                <div className="flex items-start gap-2">
                  {!n.read && (
                    <span className="mt-1.5 w-1.5 h-1.5 rounded-full bg-primary shrink-0" />
                  )}
                  <div className={cn("min-w-0 flex-1", n.read && "ml-3.5")}>
                    <p className="text-xs font-medium truncate">{n.title}</p>
                    <p className="text-[11px] text-muted-foreground mt-0.5 line-clamp-2">
                      {n.description}
                    </p>
                    <p className="text-[10px] text-muted-foreground/60 mt-1">
                      {new Date(n.timestamp).toLocaleTimeString()}
                    </p>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>

        {browserPermission === "denied" && (
          <>
            <DropdownMenuSeparator />
            <div className="px-3 py-2">
              <p className="text-[10px] text-muted-foreground">
                Browser notifications are blocked. Enable them in your browser settings.
              </p>
            </div>
          </>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
