/**
 * JARVIS Mobile Companion - Robust Connection Manager
 *
 * Implements:
 * - Exponential backoff reconnection with jitter (1s to 30s)
 * - Heartbeat keep-alive with ping/pong timeout detection
 * - Observable connection state machine: 'connecting' | 'connected' | 'reconnecting' | 'offline' | 'error'
 * - Request correlation tracking: send command with request_id and correlate response
 * - App lifecycle awareness (foreground/background transitions)
 * - Strict typing with zero `any` usage.
 */

import {
  ProtocolVersion,
  ServerMessage,
  ClientMessage,
  ClientCommandMessage,
  AssistantState
} from '../types/protocol';

export type ConnectionState = 'connecting' | 'connected' | 'reconnecting' | 'offline' | 'error';

export type ConnectionStateListener = (state: ConnectionState, detail?: string) => void;
export type MessageListener = (msg: ServerMessage) => void;

export interface ConnectionConfig {
  host: string;
  port: number;
  useSsl?: boolean;
  token?: string | null;
  clientId?: string;
  heartbeatIntervalMs?: number;
  heartbeatTimeoutMs?: number;
  maxReconnectDelayMs?: number;
}

export class RobustConnectionManager {
  private config: ConnectionConfig;
  private ws: WebSocket | null = null;
  private state: ConnectionState = 'offline';
  private reconnectAttempt = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private heartbeatInterval: ReturnType<typeof setInterval> | null = null;
  private lastPongReceived = 0;
  private isExplicitlyClosed = false;

  private stateListeners: Set<ConnectionStateListener> = new Set();
  private messageListeners: Set<MessageListener> = new Set();
  private pendingRequests: Map<string, {
    resolve: (msg: ServerMessage) => void;
    reject: (err: Error) => void;
    timer: ReturnType<typeof setTimeout>;
  }> = new Map();

  constructor(config: ConnectionConfig) {
    this.config = {
      useSsl: false,
      clientId: `mobile_${Math.random().toString(36).substring(2, 9)}`,
      heartbeatIntervalMs: 15000,
      heartbeatTimeoutMs: 10000,
      maxReconnectDelayMs: 30000,
      ...config
    };
  }

  public updateConfig(newConfig: Partial<ConnectionConfig>): void {
    const shouldReconnect =
      (newConfig.host && newConfig.host !== this.config.host) ||
      (newConfig.port && newConfig.port !== this.config.port) ||
      (newConfig.token !== undefined && newConfig.token !== this.config.token);

    this.config = { ...this.config, ...newConfig };

    if (shouldReconnect && this.state !== 'offline') {
      this.reconnect();
    }
  }

  public getState(): ConnectionState {
    return this.state;
  }

  public isConnected(): boolean {
    return this.state === 'connected' && this.ws !== null && this.ws.readyState === WebSocket.OPEN;
  }

  public subscribeState(listener: ConnectionStateListener): () => void {
    this.stateListeners.add(listener);
    listener(this.state);
    return () => this.stateListeners.delete(listener);
  }

  public subscribeMessage(listener: MessageListener): () => void {
    this.messageListeners.add(listener);
    return () => this.messageListeners.delete(listener);
  }

  private setState(newState: ConnectionState, detail?: string): void {
    if (this.state !== newState) {
      this.state = newState;
      this.stateListeners.forEach((listener) => {
        try {
          listener(newState, detail);
        } catch (e) {
          console.error('[ConnectionManager] State listener error:', e);
        }
      });
    }
  }

  public connect(): void {
    this.isExplicitlyClosed = false;
    this.clearTimers();

    if (this.ws) {
      try {
        this.ws.close();
      } catch {}
      this.ws = null;
    }

    const scheme = this.config.useSsl ? 'wss' : 'ws';
    const params = new URLSearchParams();
    if (this.config.clientId) params.set('client_id', this.config.clientId);
    if (this.config.token) params.set('token', this.config.token);

    const queryStr = params.toString() ? `?${params.toString()}` : '';
    const wsUrl = `${scheme}://${this.config.host}:${this.config.port}/ws${queryStr}`;

    this.setState(this.reconnectAttempt > 0 ? 'reconnecting' : 'connecting');

    try {
      this.ws = new WebSocket(wsUrl);
    } catch (err) {
      console.error('[ConnectionManager] Failed to create WebSocket:', err);
      this.setState('error', 'WebSocket creation failed');
      this.scheduleReconnect();
      return;
    }

    this.ws.onopen = () => {
      console.log(`[ConnectionManager] Connected to JARVIS Core at ${wsUrl}`);
      this.reconnectAttempt = 0;
      this.lastPongReceived = Date.now();
      this.setState('connected');
      this.startHeartbeat();
    };

    this.ws.onmessage = (event: MessageEvent) => {
      try {
        const raw = typeof event.data === 'string' ? event.data : '';
        if (!raw) return;

        const msg = JSON.parse(raw) as ServerMessage;

        // Track Pong responses
        if (msg.type === 'pong') {
          this.lastPongReceived = Date.now();
        }

        // Correlate with pending request if request_id matches
        if (msg.request_id && this.pendingRequests.has(msg.request_id)) {
          const req = this.pendingRequests.get(msg.request_id);
          if (req) {
            clearTimeout(req.timer);
            this.pendingRequests.delete(msg.request_id);
            req.resolve(msg);
          }
        }

        // Dispatch to all message subscribers
        this.messageListeners.forEach((listener) => {
          try {
            listener(msg);
          } catch (e) {
            console.error('[ConnectionManager] Message listener error:', e);
          }
        });
      } catch (err) {
        console.error('[ConnectionManager] Error parsing server message:', err);
      }
    };

    this.ws.onerror = (event: Event) => {
      console.warn('[ConnectionManager] WebSocket error event:', event);
      this.setState('error', 'Socket connection error');
    };

    this.ws.onclose = (event: CloseEvent) => {
      console.log(`[ConnectionManager] WebSocket closed (code=${event.code}, reason=${event.reason})`);
      this.stopHeartbeat();
      this.rejectPendingRequests('WebSocket connection closed');

      if (!this.isExplicitlyClosed) {
        this.setState('reconnecting', `Closed: ${event.reason || event.code}`);
        this.scheduleReconnect();
      } else {
        this.setState('offline', 'Explicitly disconnected');
      }
    };
  }

  public disconnect(): void {
    this.isExplicitlyClosed = true;
    this.clearTimers();
    this.rejectPendingRequests('Client disconnected explicitly');

    if (this.ws) {
      try {
        this.ws.close(1000, 'Client disconnected');
      } catch {}
      this.ws = null;
    }

    this.setState('offline', 'Disconnected by user');
  }

  public reconnect(): void {
    this.disconnect();
    this.connect();
  }

  public handleAppForeground(): void {
    if (this.state === 'offline' || this.state === 'error' || !this.isConnected()) {
      console.log('[ConnectionManager] Foreground trigger: Fast reconnecting...');
      this.reconnectAttempt = 0;
      this.connect();
    }
  }

  public handleAppBackground(): void {
    // Keep connection alive but relax heartbeat if needed
    console.log('[ConnectionManager] App entered background.');
  }

  private scheduleReconnect(): void {
    if (this.reconnectTimer) return;

    this.reconnectAttempt++;
    // Exponential backoff: 1s, 2s, 4s, 8s... up to maxReconnectDelayMs with +/- 20% jitter
    const baseDelay = Math.min(1000 * Math.pow(1.8, this.reconnectAttempt - 1), this.config.maxReconnectDelayMs || 30000);
    const jitter = baseDelay * (0.8 + Math.random() * 0.4);
    const delay = Math.round(jitter);

    console.log(`[ConnectionManager] Reconnecting in ${delay}ms (attempt #${this.reconnectAttempt})`);

    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      if (!this.isExplicitlyClosed) {
        this.connect();
      }
    }, delay);
  }

  private startHeartbeat(): void {
    this.stopHeartbeat();
    const interval = this.config.heartbeatIntervalMs || 15000;
    const timeout = this.config.heartbeatTimeoutMs || 10000;

    this.heartbeatInterval = setInterval(() => {
      if (!this.isConnected()) return;

      const now = Date.now();
      if (now - this.lastPongReceived > interval + timeout) {
        console.warn('[ConnectionManager] Heartbeat timeout! Missed server pong. Dropping connection to trigger reconnect.');
        if (this.ws) {
          try {
            this.ws.close(4000, 'Heartbeat timeout');
          } catch {}
        }
        return;
      }

      this.send({
        version: '1',
        type: 'ping',
        request_id: `ping_${now}`,
        data: { timestamp: now }
      });
    }, interval);
  }

  private stopHeartbeat(): void {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
    }
  }

  private clearTimers(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.stopHeartbeat();
  }

  private rejectPendingRequests(reason: string): void {
    this.pendingRequests.forEach((req) => {
      clearTimeout(req.timer);
      req.reject(new Error(reason));
    });
    this.pendingRequests.clear();
  }

  public send(message: ClientMessage): boolean {
    if (!this.isConnected() || !this.ws) {
      console.warn('[ConnectionManager] Cannot send message: WebSocket is not open.');
      return false;
    }

    try {
      this.ws.send(JSON.stringify(message));
      return true;
    } catch (err) {
      console.error('[ConnectionManager] Failed to send message:', err);
      return false;
    }
  }

  public sendCommandCorrelated(text: string, conversationId?: string | number | null, timeoutMs = 25000): Promise<ServerMessage> {
    const requestId = `cmd_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`;
    const msg: ClientCommandMessage = {
      version: '1',
      type: 'command',
      request_id: requestId,
      session_id: this.config.clientId,
      data: {
        text,
        conversation_id: conversationId
      }
    };

    return new Promise<ServerMessage>((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pendingRequests.delete(requestId);
        reject(new Error(`Command '${text.substring(0, 30)}...' timed out after ${timeoutMs}ms`));
      }, timeoutMs);

      this.pendingRequests.set(requestId, { resolve, reject, timer });

      const sent = this.send(msg);
      if (!sent) {
        clearTimeout(timer);
        this.pendingRequests.delete(requestId);
        reject(new Error('Failed to send command: Connection offline'));
      }
    });
  }
}
