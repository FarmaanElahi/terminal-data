import { useEffect, useRef } from "react";
import { useAuthStore } from "@/stores/auth-store";
import { useLayoutStore } from "@/stores/layout-store";
import { useSaveLayoutMutation } from "@/queries/use-layout";

/**
 * Zero-render component that debounces layout changes and persists them
 * to the server. Uses Zustand's subscribe (not a hook) so it causes no
 * re-renders.
 */
export function LayoutSync() {
  const isBooted = useAuthStore((s) => s.isBooted);
  const saveMutation = useSaveLayoutMutation();
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const saveRef = useRef(saveMutation.mutate);
  saveRef.current = saveMutation.mutate;

  useEffect(() => {
    if (!isBooted) return;

    const unsubscribe = useLayoutStore.subscribe((state) => {
      const snapshot = {
        layouts: state.layouts,
        activeLayoutId: state.activeLayoutId,
        channelContexts: state.channelContexts,
        globalContext: state.globalContext,
        theme: state.theme,
        // Intentionally omit maximizedPaneId — transient UI state
      };

      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => {
        saveRef.current(snapshot);
      }, 1000);
    });

    return () => {
      unsubscribe();
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [isBooted]);

  return null;
}
