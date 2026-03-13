import { useAuthStore } from "@/stores/auth-store";
import { Loader2 } from "lucide-react";

export function BootLoader() {
  const isBooted = useAuthStore((s) => s.isBooted);
  const isLoading = useAuthStore((s) => s.isLoading);
  const token = useAuthStore((s) => s.token);

  // Show only when there is an active loading operation:
  //   - isLoading=true  → login/register form submission in progress
  //   - token && !isBooted → page-reload boot (handled upstream by AuthLoader,
  //                          but guard here too for safety)
  // Critically: do NOT show when there is no token — that means the user is
  // unauthenticated and should see the login page, not a spinner.
  if (!isLoading && (isBooted || !token)) {
    return null;
  }

  return (
    <div
      className="fixed inset-0 bg-background z-50 flex flex-col items-center justify-center"
      style={{
        pointerEvents: isBooted ? "none" : "auto",
      }}
    >
      {/* Loading content */}
      <div className="flex flex-col items-center gap-4">
        {/* Spinner icon with rotation animation */}
        <Loader2 className="h-8 w-8 text-primary animate-spin" strokeWidth={1.5} />

        {/* Loading text */}
        <div className="text-center">
          <p className="text-sm text-foreground font-medium">Initializing Terminal</p>
          <p className="text-xs text-muted-foreground mt-1">Loading markets & configuration...</p>
        </div>

        {/* Progress indicator - subtle dot animation */}
        <div className="flex gap-1">
          <div
            className="h-1.5 w-1.5 rounded-full bg-primary/80"
            style={{
              animation: "pulse 1.5s cubic-bezier(0.4, 0, 0.6, 1) infinite",
              animationDelay: "0ms",
            }}
          />
          <div
            className="h-1.5 w-1.5 rounded-full bg-primary/60"
            style={{
              animation: "pulse 1.5s cubic-bezier(0.4, 0, 0.6, 1) infinite",
              animationDelay: "200ms",
            }}
          />
          <div
            className="h-1.5 w-1.5 rounded-full bg-primary/40"
            style={{
              animation: "pulse 1.5s cubic-bezier(0.4, 0, 0.6, 1) infinite",
              animationDelay: "400ms",
            }}
          />
        </div>
      </div>
    </div>
  );
}
