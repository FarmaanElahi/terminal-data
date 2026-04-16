import { create } from "zustand";
import { persist } from "zustand/middleware";

export interface AppNotification {
  id: string;
  type: "alert_triggered" | "alert_status_changed";
  title: string;
  description: string;
  timestamp: string;
  read: boolean;
}

interface NotificationsState {
  notifications: AppNotification[];
  browserPermission: NotificationPermission;
  addNotification: (n: Omit<AppNotification, "read">) => void;
  markAllRead: () => void;
  clearAll: () => void;
  setBrowserPermission: (p: NotificationPermission) => void;
}

const MAX_NOTIFICATIONS = 50;

export const useNotificationsStore = create<NotificationsState>()(
  persist(
    (set) => ({
      notifications: [],
      browserPermission: "default",

      addNotification: (n) =>
        set((state) => {
          const next: AppNotification = { ...n, read: false };
          const updated = [next, ...state.notifications].slice(
            0,
            MAX_NOTIFICATIONS,
          );
          return { notifications: updated };
        }),

      markAllRead: () =>
        set((state) => ({
          notifications: state.notifications.map((n) => ({ ...n, read: true })),
        })),

      clearAll: () => set({ notifications: [] }),

      setBrowserPermission: (browserPermission) =>
        set({ browserPermission }),
    }),
    {
      name: "terminal-notifications",
      partialize: (state) => ({
        notifications: state.notifications,
        browserPermission: state.browserPermission,
      }),
    },
  ),
);
