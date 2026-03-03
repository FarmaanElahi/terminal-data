import { useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { useUpstoxStatus } from "@/hooks/use-upstox-status";

export function UpstoxLoginDialog() {
  const { data, openLogin } = useUpstoxStatus();
  const [open, setOpen] = useState(false);

  // Auto-show when login is required; auto-dismiss when connected
  useEffect(() => {
    if (data?.login_required && !data?.connected) {
      setOpen(true);
    } else if (data?.connected) {
      setOpen(false);
    }
  }, [data?.login_required, data?.connected]);

  // Listen for postMessage from the OAuth popup
  useEffect(() => {
    function onMessage(event: MessageEvent) {
      if (event.data?.type === "upstox-login-success") {
        setOpen(false);
      }
    }
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, []);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Connect Upstox Account</DialogTitle>
          <DialogDescription>
            Login to your Upstox account to enable real-time chart data for
            Indian markets (NSE/BSE).
          </DialogDescription>
        </DialogHeader>
        <DialogFooter className="flex gap-2 sm:justify-start">
          <Button onClick={openLogin}>Login to Upstox</Button>
          <Button variant="ghost" onClick={() => setOpen(false)}>
            Later
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
