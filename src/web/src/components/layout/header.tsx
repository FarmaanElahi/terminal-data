import { useNavigate } from "react-router-dom";
import { useState } from "react";
import { useAuthStore } from "@/stores/auth-store";
import { useLayoutStore } from "@/stores/layout-store";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { AddWidgetDialog } from "@/components/dashboard/add-widget-dialog";
import { LayoutTabsList } from "@/components/dashboard/layout-tabs-bar";
import { Plus, Moon, Sun } from "lucide-react";

export function AppHeader() {
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const theme = useLayoutStore((s) => s.theme);
  const setTheme = useLayoutStore((s) => s.setTheme);
  const navigate = useNavigate();
  const [addWidgetOpen, setAddWidgetOpen] = useState(false);

  return (
    <>
      <header className="h-8 border-b border-border flex items-center px-2 gap-2 bg-card shrink-0">
        {/* Logo */}
        <div className="flex items-center gap-1.5 shrink-0 mr-2">
          <div className="w-4 h-4 bg-primary flex items-center justify-center rounded-sm">
            <span className="text-primary-foreground font-bold font-mono leading-none text-[9px]">
              T
            </span>
          </div>
          <span className="font-mono text-[10px] tracking-[0.25em] uppercase text-foreground/80 hidden sm:inline">
            TERMINAL
          </span>
        </div>

        {/* Layout tabs — center, scrollable */}
        <div className="flex-1 flex items-center overflow-x-auto scrollbar-none min-w-0">
          <LayoutTabsList />
        </div>

        {/* Right controls */}
        <div className="flex items-center gap-0.5 shrink-0">
          <Button
            variant="ghost"
            size="sm"
            className="h-6 text-xs gap-1 px-2"
            onClick={() => setAddWidgetOpen(true)}
          >
            <Plus className="w-3 h-3" />
            <span className="hidden sm:inline">Add Widget</span>
          </Button>

          <Button
            variant="ghost"
            size="icon"
            className="h-6 w-6"
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
            title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
          >
            {theme === "dark" ? (
              <Sun className="w-3.5 h-3.5" />
            ) : (
              <Moon className="w-3.5 h-3.5" />
            )}
          </Button>

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" className="h-6 w-6">
                <div className="w-5 h-5 rounded-sm bg-primary/20 flex items-center justify-center text-[10px] font-medium text-primary font-mono">
                  {user?.username?.[0]?.toUpperCase() ?? "?"}
                </div>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-48">
              <div className="px-2 py-1.5">
                <p className="text-sm font-medium">{user?.username ?? "User"}</p>
                <p className="text-xs text-muted-foreground font-mono">Active</p>
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
        </div>
      </header>

      <AddWidgetDialog open={addWidgetOpen} onClose={() => setAddWidgetOpen(false)} />
    </>
  );
}
