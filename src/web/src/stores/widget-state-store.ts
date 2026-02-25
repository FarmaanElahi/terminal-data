import { create } from "zustand";

/**
 * Framework-level widget state store.
 *
 * Each widget instance gets a keyed state bucket (identified by instanceId).
 * State here survives:
 *   - Component unmount/remount (tab switch, float, dock, split)
 *   - Layout mutations (moving, resizing, removing other panes)
 *   - Page is NOT persisted to localStorage (runtime data only)
 *
 * Widgets use the `useWidgetState` hook to read/write from this store
 * instead of React's useState for any data that should survive remounts
 * (fetched data, WebSocket session IDs, scroll positions, etc.).
 */

interface WidgetStateStore {
  /** instanceId → { key → value } */
  states: Record<string, Record<string, unknown>>;

  /** Set a single key on an instance's state */
  set: (instanceId: string, key: string, value: unknown) => void;

  /** Merge multiple keys into an instance's state */
  merge: (instanceId: string, patch: Record<string, unknown>) => void;

  /** Read a key from an instance's state */
  get: (instanceId: string, key: string) => unknown;

  /** Clear all state for an instance (call when widget is removed) */
  clear: (instanceId: string) => void;
}

export const useWidgetStateStore = create<WidgetStateStore>((set, get) => ({
  states: {},

  set: (instanceId, key, value) => {
    set((state) => ({
      states: {
        ...state.states,
        [instanceId]: {
          ...state.states[instanceId],
          [key]: value,
        },
      },
    }));
  },

  merge: (instanceId, patch) => {
    set((state) => {
      const currentInstance = state.states[instanceId] || {};
      const resolvedPatch: Record<string, unknown> = {};

      for (const [key, val] of Object.entries(patch)) {
        if (typeof val === "function") {
          resolvedPatch[key] = val(currentInstance[key]);
        } else {
          resolvedPatch[key] = val;
        }
      }

      return {
        states: {
          ...state.states,
          [instanceId]: {
            ...currentInstance,
            ...resolvedPatch,
          },
        },
      };
    });
  },

  get: (instanceId, key) => {
    return get().states[instanceId]?.[key];
  },

  clear: (instanceId) => {
    set((state) => {
      const { [instanceId]: _, ...rest } = state.states;
      return { states: rest };
    });
  },
}));
