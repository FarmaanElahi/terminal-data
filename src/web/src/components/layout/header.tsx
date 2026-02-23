import { useNavigate } from "react-router-dom";
import { useState } from "react";
import { useAuthStore } from "@/stores/auth-store";
import { useUIStore } from "@/stores/ui-store";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useEffect } from "react";
import { AddWidgetDialog } from "@/components/dashboard/add-widget-dialog";
import { Plus } from "lucide-react";

export function AppHeader() {
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const setCommandPaletteOpen = useUIStore((s) => s.setCommandPaletteOpen);
  const navigate = useNavigate();
  const [addWidgetOpen, setAddWidgetOpen] = useState(false);

  // Global keyboard shortcut: Cmd+K / Ctrl+K
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setCommandPaletteOpen(true);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [setCommandPaletteOpen]);

  return (
    <>
      <header className="h-12 border-b border-border flex items-center px-3 gap-2 bg-card/50 backdrop-blur-sm shrink-0">
        {/* Logo */}
        <div className="flex items-center gap-1.5 mr-4">
          <div className="w-6 h-6 rounded bg-primary flex items-center justify-center">
            <svg
              className="w-3.5 h-3.5 text-primary-foreground"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={2}
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M3.75 3v11.25A2.25 2.25 0 006 16.5h2.25M3.75 3h-1.5m1.5 0h16.5m0 0h1.5m-1.5 0v11.25A2.25 2.25 0 0118 16.5h-2.25m-7.5 0h7.5m-7.5 0l-1 3m8.5-3l1 3m0 0l.5 1.5m-.5-1.5h-9.5m0 0l-.5 1.5m.75-9l3-3 2.148 2.148A12.061 12.061 0 0116.5 7.605"
              />
            </svg>
          </div>
          <span className="text-sm font-semibold tracking-tight">Terminal</span>
        </div>

        {/* Search trigger */}
        <Button
          variant="outline"
          className="h-8 w-64 justify-start text-muted-foreground text-xs bg-background/50 border-border/50"
          onClick={() => setCommandPaletteOpen(true)}
        >
          <svg
            className="w-3.5 h-3.5 mr-2"
            fill="none"
            viewBox="0 0 24 24"
            strokeWidth={1.5}
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="m21 21-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z"
            />
          </svg>
          Search symbols...
          <kbd className="ml-auto text-[10px] font-mono bg-muted px-1.5 py-0.5 rounded text-muted-foreground">
            ⌘K
          </kbd>
        </Button>

        {/* Spacer */}
        <div className="flex-1" />

        {/* Add Widget Button */}
        <Button
          variant="outline"
          size="sm"
          className="h-8 text-xs gap-1.5"
          onClick={() => setAddWidgetOpen(true)}
        >
          <Plus className="w-3.5 h-3.5" />
          Add Widget
        </Button>

        {/* User menu */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 rounded-full"
            >
              <div className="w-6 h-6 rounded-full bg-primary/20 flex items-center justify-center text-xs font-medium text-primary">
                {user?.username?.[0]?.toUpperCase() ?? "?"}
              </div>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-48">
            <div className="px-2 py-1.5">
              <p className="text-sm font-medium">{user?.username ?? "User"}</p>
              <p className="text-xs text-muted-foreground">Active</p>
            </div>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              onClick={() => {
                logout();
                navigate("/login");
              }}
            >
              Sign out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </header>

      {/* Global Add Widget dialog */}
      <AddWidgetDialog
        open={addWidgetOpen}
        onClose={() => setAddWidgetOpen(false)}
      />
    </>
  );
}
