import type { WSMessage } from "@/types/ws";

type MessageHandler = (message: WSMessage) => void;

/**
 * Multiplexed WebSocket client with auto-reconnect, heartbeat,
 * and a pending-message queue to avoid the send-before-open race.
 */
export class TerminalWebSocket {
  private ws: WebSocket | null = null;
  private handlers = new Map<string, Set<MessageHandler>>();
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 10;
  private pingInterval: ReturnType<typeof setInterval> | null = null;
  private token: string | null = null;
  private _isConnected = false;

  /** Messages queued while the socket is still connecting */
  private pendingQueue: WSMessage[] = [];

  get isConnected(): boolean {
    return this._isConnected;
  }

  connect(token: string): void {
    // If already connected or connecting with the same token, skip
    if (
      this.ws &&
      (this.ws.readyState === WebSocket.CONNECTING ||
        this.ws.readyState === WebSocket.OPEN) &&
      this.token === token
    ) {
      return;
    }

    // Tear down any existing connection first
    if (this.ws) {
      this.ws.onopen = null;
      this.ws.onmessage = null;
      this.ws.onclose = null;
      this.ws.onerror = null;
      if (
        this.ws.readyState === WebSocket.OPEN ||
        this.ws.readyState === WebSocket.CONNECTING
      ) {
        this.ws.close(1000, "Reconnecting");
      }
      this.ws = null;
    }

    this.token = token;
    this.reconnectAttempts = 0;
    this._connect();
  }

  private _connect(): void {
    if (!this.token) return;

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.host;
    const ws = new WebSocket(`${protocol}//${host}/ws?token=${this.token}`);
    this.ws = ws;

    ws.onopen = () => {
      // Guard: make sure this is still the active socket
      if (this.ws !== ws) return;

      this._isConnected = true;
      this.reconnectAttempts = 0;
      this.startPingLoop();
      console.log("[WS] Connected");

      // Flush pending queue using this specific socket instance
      this.flushPendingQueue(ws);
    };

    ws.onmessage = (event: MessageEvent) => {
      if (this.ws !== ws) return;
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

    ws.onclose = (event) => {
      if (this.ws !== ws) return;

      this._isConnected = false;
      this.stopPingLoop();
      console.log(`[WS] Disconnected (code: ${event.code})`);

      // Don't reconnect on intentional close or auth failure
      if (event.code === 4401 || event.code === 1000) return;

      this.attemptReconnect();
    };

    ws.onerror = (err) => {
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

  /** Drain the pending queue using a specific socket instance */
  private flushPendingQueue(ws: WebSocket): void {
    while (this.pendingQueue.length > 0) {
      if (ws.readyState !== WebSocket.OPEN) {
        console.warn("[WS] Socket not open during flush, stopping");
        break;
      }
      const msg = this.pendingQueue.shift()!;
      console.log("[WS] Flushing queued message:", msg.m);
      ws.send(JSON.stringify(msg));
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

  /**
   * Send a message. If the socket isn't open yet (still CONNECTING),
   * the message is queued and will be flushed automatically on open.
   */
  send(msg: WSMessage): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(msg));
    } else if (this.ws?.readyState === WebSocket.CONNECTING) {
      console.log("[WS] Queuing message (socket connecting):", msg.m);
      this.pendingQueue.push(msg);
    } else {
      console.warn("[WS] Cannot send, not connected");
    }
  }

  disconnect(): void {
    this.token = null;
    this.pendingQueue = [];
    this.stopPingLoop();
    if (this.ws) {
      this.ws.onopen = null;
      this.ws.onmessage = null;
      this.ws.onclose = null;
      this.ws.onerror = null;
      this.ws.close(1000, "User disconnect");
      this.ws = null;
    }
    this._isConnected = false;
  }
}

// Singleton instance
export const terminalWS = new TerminalWebSocket();
