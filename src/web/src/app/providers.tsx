import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";
import { TooltipProvider } from "@/components/ui/tooltip";
import { useEffect } from "react";
import { useAuthStore } from "@/stores/auth-store";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
    },
  },
});

function AuthLoader({ children }: { children: React.ReactNode }) {
  const loadBoot = useAuthStore((s) => s.loadBoot);
  const token = useAuthStore((s) => s.token);

  useEffect(() => {
    if (token) {
      loadBoot();
    }
  }, []);

  return <>{children}</>;
}

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <TooltipProvider>
          <AuthLoader>{children}</AuthLoader>
        </TooltipProvider>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
