import type { WSMessage } from "@/types/ws";

type MessageHandler = (message: WSMessage) => void;

/**
 * Multiplexed WebSocket client with auto-reconnect and heartbeat.
 * Singleton — one connection per browser tab.
 */
export class TerminalWebSocket {
  private ws: WebSocket | null = null;
  private handlers = new Map<string, Set<MessageHandler>>();
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 10;
  private pingInterval: ReturnType<typeof setInterval> | null = null;
  private token: string | null = null;
  private _isConnected = false;

  get isConnected(): boolean {
    return this._isConnected;
  }

  connect(token: string): void {
    this.token = token;
    this.reconnectAttempts = 0;
    this._connect();
  }

  private _connect(): void {
    if (!this.token) return;

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.host;
    this.ws = new WebSocket(`${protocol}//${host}/ws?token=${this.token}`);

    this.ws.onopen = () => {
      this._isConnected = true;
      this.reconnectAttempts = 0;
      this.startPingLoop();
      console.log("[WS] Connected");
    };

    this.ws.onmessage = (event: MessageEvent) => {
      try {
        const msg: WSMessage = JSON.parse(event.data as string);
        const handlers = this.handlers.get(msg.m);
        if (handlers) {
          handlers.forEach((h) => h(msg));
        }
      } catch (err) {
        console.error("[WS] Failed to parse message:", err);
      }
    };

    this.ws.onclose = (event) => {
      this._isConnected = false;
      this.stopPingLoop();
      console.log(`[WS] Disconnected (code: ${event.code})`);

      // Don't reconnect on intentional close or auth failure
      if (event.code === 4401 || event.code === 1000) return;

      this.attemptReconnect();
    };

    this.ws.onerror = (err) => {
      console.error("[WS] Error:", err);
    };
  }

  private attemptReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.warn("[WS] Max reconnect attempts reached");
      return;
    }
    const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000);
    this.reconnectAttempts++;
    console.log(
      `[WS] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`,
    );
    setTimeout(() => this._connect(), delay);
  }

  private startPingLoop(): void {
    this.stopPingLoop();
    this.pingInterval = setInterval(() => {
      this.send({ m: "ping" });
    }, 30000);
  }

  private stopPingLoop(): void {
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
    }
  }

  /**
   * Subscribe to a message type. Returns an unsubscribe function.
   */
  on(messageType: string, handler: MessageHandler): () => void {
    if (!this.handlers.has(messageType)) {
      this.handlers.set(messageType, new Set());
    }
    this.handlers.get(messageType)!.add(handler);

    return () => {
      this.handlers.get(messageType)?.delete(handler);
    };
  }

  send(msg: WSMessage): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(msg));
    } else {
      console.warn("[WS] Cannot send, not connected");
    }
  }

  disconnect(): void {
    this.token = null;
    this.stopPingLoop();
    if (this.ws) {
      this.ws.close(1000, "User disconnect");
      this.ws = null;
    }
    this._isConnected = false;
  }
}

// Singleton instance
export const terminalWS = new TerminalWebSocket();
