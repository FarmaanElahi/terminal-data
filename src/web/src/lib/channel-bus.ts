import type { ChannelColor, ChannelEvent } from "@/types/layout";

type ChannelHandler = (event: ChannelEvent) => void;

/**
 * Simple pub/sub event bus for cross-widget channel linking.
 * Panes are assigned a color channel; events broadcast to all
 * panes on the same channel.
 */
class ChannelBus {
  private listeners = new Map<ChannelColor, Set<ChannelHandler>>();

  subscribe(channel: ChannelColor, handler: ChannelHandler): () => void {
    if (!this.listeners.has(channel)) {
      this.listeners.set(channel, new Set());
    }
    this.listeners.get(channel)!.add(handler);

    return () => {
      this.listeners.get(channel)?.delete(handler);
    };
  }

  broadcast(event: ChannelEvent): void {
    const handlers = this.listeners.get(event.channel);
    if (handlers) {
      handlers.forEach((h) => h(event));
    }
  }
}

export const channelBus = new ChannelBus();
