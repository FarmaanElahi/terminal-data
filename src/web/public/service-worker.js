/**
 * Service Worker for Web Push Notifications.
 *
 * This worker runs in the background and can receive push events
 * even when the web application is not open.
 */

/* eslint-disable no-restricted-globals */

// Listen for push events from the server
self.addEventListener("push", (event) => {
  /** @type {PushEvent} */
  const pushEvent = event;

  let data = {
    title: "🔔 Alert Triggered",
    body: "An alert condition has been met.",
    icon: "/favicon.ico",
    data: {},
  };

  if (pushEvent.data) {
    try {
      data = { ...data, ...pushEvent.data.json() };
    } catch {
      data.body = pushEvent.data.text();
    }
  }

  const options = {
    body: data.body,
    icon: data.icon || "/favicon.ico",
    badge: "/favicon.ico",
    data: data.data || {},
    vibrate: [100, 50, 100],
    actions: [
      { action: "open", title: "Open" },
      { action: "dismiss", title: "Dismiss" },
    ],
    tag: `alert-${Date.now()}`,
    renotify: true,
  };

  event.waitUntil(self.registration.showNotification(data.title, options));
});

// Handle notification click
self.addEventListener("notificationclick", (event) => {
  event.notification.close();

  if (event.action === "dismiss") return;

  // Open the app or focus existing window
  event.waitUntil(
    self.clients
      .matchAll({ type: "window", includeUncontrolled: true })
      .then((clientList) => {
        // Focus an existing window if available
        for (const client of clientList) {
          if (client.url.includes(self.location.origin) && "focus" in client) {
            return client.focus();
          }
        }
        // Otherwise open a new window
        return self.clients.openWindow("/");
      }),
  );
});

// Handle service worker activation
self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});
