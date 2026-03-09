import { CommandPalette } from "./command-palette";
import { useSaveToWatchlist } from "@/hooks/use-save-to-watchlist";
import { useAlertNotifications } from "@/hooks/use-alert-notifications";

export function AppLayout({ children }: { children: React.ReactNode }) {
  useSaveToWatchlist();
  useAlertNotifications();

  return (
    <div className="h-screen flex flex-col bg-background overflow-hidden">
      <CommandPalette />
      <main className="flex-1 overflow-hidden">{children}</main>
    </div>
  );
}
