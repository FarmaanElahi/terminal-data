import { QueryClient, QueryClientProvider, useQueryClient } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";
import { TooltipProvider } from "@/components/ui/tooltip";
import { useEffect } from "react";
import { useAuthStore } from "@/stores/auth-store";
import { Toaster } from "@/components/ui/sonner";
import { LayoutSync } from "@/components/layout/layout-sync";
import { BrokerLoginDialog } from "@/components/layout/broker-login-dialog";
import { BootLoader } from "@/components/layout/boot-loader";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: Infinity,
      refetchOnWindowFocus: false,
      refetchOnReconnect: false,
      retry: 1,
    },
  },
});

function AuthLoader({ children }: { children: React.ReactNode }) {
  const loadBoot = useAuthStore((s) => s.loadBoot);
  const token = useAuthStore((s) => s.token);
  const isBooted = useAuthStore((s) => s.isBooted);
  const qc = useQueryClient();

  useEffect(() => {
    if (token) {
      loadBoot(qc);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Don't mount children until boot completes — prevents query hooks from
  // firing before the cache is seeded, which would cause duplicate requests.
  if (token && !isBooted) {
    return <BootLoader />;
  }

  return (
    <>
      {children}
      <BootLoader />
      <LayoutSync />
      <BrokerLoginDialog />
    </>
  );
}

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <TooltipProvider>
          <AuthLoader>{children}</AuthLoader>
          <Toaster position="bottom-left" richColors closeButton />
        </TooltipProvider>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
