import { AppHeader } from "./header";
import { CommandPalette } from "./command-palette";

export function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="h-screen flex flex-col bg-background overflow-hidden">
      <AppHeader />
      <CommandPalette />
      <main className="flex-1 overflow-hidden">{children}</main>
    </div>
  );
}
