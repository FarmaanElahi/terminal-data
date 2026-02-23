import { useCallback, useRef } from "react";
import { useWidgetStateStore } from "@/stores/widget-state-store";

/**
 * Framework hook — drop-in replacement for useState that persists across remounts.
 *
 * Widget state is stored in a Zustand store keyed by (instanceId, key).
 * When the widget component unmounts and remounts (due to tab switch, float,
 * dock, split, etc.), the state is instantly restored from the store.
 *
 * @example
 * ```tsx
 * function MyWidget({ instanceId }: WidgetProps) {
 *   const [data, setData] = useWidgetState(instanceId, "data", []);
 *   const [isLoading, setIsLoading] = useWidgetState(instanceId, "isLoading", true);
 *
 *   useEffect(() => {
 *     if (data.length > 0) return; // already have cached data
 *     fetchData().then(d => { setData(d); setIsLoading(false); });
 *   }, []);
 * }
 * ```
 */
export function useWidgetState<T>(
  instanceId: string,
  key: string,
  initialValue: T,
): [T, (value: T | ((prev: T) => T)) => void] {
  // Read from the global widget state store
  const storedValue = useWidgetStateStore(
    (s) => s.states[instanceId]?.[key] as T | undefined,
  );

  // Use stored value if it exists, otherwise fall back to initial
  const value = storedValue !== undefined ? storedValue : initialValue;

  // Keep initialValue in a ref so the setter callback is stable
  const initialRef = useRef(initialValue);
  initialRef.current = initialValue;

  const setValue = useCallback(
    (newValue: T | ((prev: T) => T)) => {
      const store = useWidgetStateStore.getState();
      const current = store.states[instanceId]?.[key] as T | undefined;
      const currentValue = current !== undefined ? current : initialRef.current;

      const resolved =
        typeof newValue === "function"
          ? (newValue as (prev: T) => T)(currentValue)
          : newValue;

      store.set(instanceId, key, resolved);
    },
    [instanceId, key],
  );

  return [value, setValue];
}

/**
 * Merge multiple state keys at once (avoids multiple re-renders).
 *
 * @example
 * ```tsx
 * const mergeState = useWidgetStateMerge(instanceId);
 * mergeState({ tickers: newTickers, values: newValues, isLoading: false });
 * ```
 */
export function useWidgetStateMerge(instanceId: string) {
  return useCallback(
    (patch: Record<string, unknown>) => {
      useWidgetStateStore.getState().merge(instanceId, patch);
    },
    [instanceId],
  );
}
