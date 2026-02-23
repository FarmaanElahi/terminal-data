import { AppSidebar } from "./app-sidebar";
import { AppHeader } from "./header";
import { CommandPalette } from "./command-palette";
import { useUIStore } from "@/stores/ui-store";

export function AppLayout({ children }: { children: React.ReactNode }) {
  const sidebarOpen = useUIStore((s) => s.sidebarOpen);

  return (
    <div className="h-screen flex flex-col bg-background overflow-hidden">
      <AppHeader />
      <CommandPalette />
      <div className="flex flex-1 overflow-hidden">
        <AppSidebar open={sidebarOpen} />
        <main className="flex-1 overflow-auto scrollbar-thin">{children}</main>
      </div>
    </div>
  );
}
