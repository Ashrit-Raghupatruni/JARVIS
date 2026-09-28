/**
 * JARVIS Mobile Companion - Network API & WebSocket Client
 */

import { RobustConnectionManager } from '../services/connectionManager';
import { RuntimeDiagnostics } from '../types/protocol';

export interface SystemTelemetryData {
  timestamp: number;
  cpu_percent: number;
  ram_percent: number;
  ram_used_gb: number;
  ram_total_gb: number;
  gpu_percent: number;
  battery_percent?: number;
  battery_plugged?: boolean;
  active_task: string;
  active_workflow: string;
  active_llm_provider: string;
  assistant_state: string;
  internet_connected: boolean;
}

export interface MobileApprovalItem {
  approval_id: string;
  action_type: string;
  description: string;
  dangerous_target: string;
  challenge?: string;
  timestamp: number;
  timeout_seconds: number;
}

export interface ConversationListItem {
  id: number;
  title: string;
  summary?: string;
  message_count?: number;
  created_at: string;
  updated_at: string;
}

export interface ConversationDetail {
  id: number;
  title: string;
  messages: Array<{
    id: string;
    role: 'user' | 'assistant' | 'system';
    content: string;
    timestamp: string;
  }>;
}

export interface LiveModeFrameData {
  is_live_mode_enabled: boolean;
  active_app: string;
  window_title: string;
  active_workflow?: string;
  current_step?: string;
  proactive_suggestion?: string;
  detected_form_fields?: number;
  confidence_score?: number;
  window_bounds?: {
    x: number;
    y: number;
    w: number;
    h: number;
  } | null;
}

export interface LiveModeStatusResponse {
  status: string;
  live_mode_enabled: boolean;
  frame?: LiveModeFrameData | null;
}

export class JarvisMobileClient {
  private serverHost: string;
  private serverPort: number;
  private useSsl: boolean;
  private token: string | null = null;
  private ws: WebSocket | null = null;
  private connectionManager: RobustConnectionManager | null = null;

  constructor(serverHost = "10.0.2.2", serverPort = 8000, useSsl = false) {
    this.serverHost = serverHost;
    this.serverPort = serverPort;
    this.useSsl = useSsl;
  }

  setServerAddress(host: string, port: number = 8000, useSsl: boolean = false) {
    this.serverHost = host;
    this.serverPort = port;
    this.useSsl = useSsl;
    if (this.connectionManager) {
      this.connectionManager.updateConfig({ host, port, useSsl });
    }
  }

  getHost(): string {
    return this.serverHost;
  }

  getPort(): number {
    return this.serverPort;
  }

  setAuthToken(token: string) {
    this.token = token;
    if (this.connectionManager) {
      this.connectionManager.updateConfig({ token });
    }
  }

  getConnectionManager(): RobustConnectionManager {
    if (!this.connectionManager) {
      this.connectionManager = new RobustConnectionManager({
        host: this.serverHost,
        port: this.serverPort,
        useSsl: this.useSsl,
        token: this.token
      });
    }
    return this.connectionManager;
  }

  get baseUrl() {
    const scheme = this.useSsl ? "https" : "http";
    return `${scheme}://${this.serverHost}:${this.serverPort}`;
  }

  get wsUrl() {
    const scheme = this.useSsl ? "wss" : "ws";
    return `${scheme}://${this.serverHost}:${this.serverPort}/api/v1/mobile/ws`;
  }

  // ── Unified Core Endpoints ──────────────────────────────────────────────
  async fetchHealth() {
    const res = await this.fetchWithTimeout(`${this.baseUrl}/health`);
    return res.json();
  }

  async fetchSystemStatus(): Promise<RuntimeDiagnostics> {
    const res = await this.fetchWithTimeout(`${this.baseUrl}/system/status`);
    return res.json();
  }

  async fetchDeviceInfo(): Promise<Record<string, unknown>> {
    const res = await this.fetchWithTimeout(`${this.baseUrl}/device/info`);
    return res.json();
  }

  async pairDeviceUnified(payload: Record<string, unknown>) {
    const res = await this.fetchWithTimeout(`${this.baseUrl}/device/pair`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (data.token || data.access_token) {
      this.setAuthToken(data.token || data.access_token);
    }
    return data;
  }

  async sendRootCommand(text: string, conversationId?: string | number | null) {
    const res = await this.fetchWithTimeout(`${this.baseUrl}/command`, {
      method: "POST",
      headers: this.getHeaders(),
      body: JSON.stringify({ text, conversation_id: conversationId })
    });
    return res.json();
  }

  async updateRootSettings(settings: Record<string, unknown>) {
    const res = await this.fetchWithTimeout(`${this.baseUrl}/settings`, {
      method: "POST",
      headers: this.getHeaders(),
      body: JSON.stringify(settings)
    });
    return res.json();
  }

  private async fetchWithTimeout(url: string, options: RequestInit = {}, timeoutMs = 8000): Promise<Response> {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const res = await fetch(url, { ...options, signal: controller.signal });
      return res;
    } finally {
      clearTimeout(timeoutId);
    }
  }

  private getHeaders() {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (this.token) {
      headers["Authorization"] = `Bearer ${this.token}`;
    }
    return headers;
  }

  async pairDevice(deviceName: string, deviceId: string, pairingCode: string, session_id: string) {
    const res = await this.fetchWithTimeout(`${this.baseUrl}/api/v1/mobile/pair/confirm`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        pairing_session_id: session_id,
        pairing_code: pairingCode,
        device_id: deviceId
      })
    });
    const data = await res.json();
    if (data.access_token || data.token) {
      this.setAuthToken(data.access_token || data.token);
    }
    return data;
  }

  async easyPair(pin: string, deviceName: string = "Android Phone", deviceId: string = "android-companion-1") {
    const res = await this.fetchWithTimeout(`${this.baseUrl}/api/v1/mobile/pair`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pin, device_name: deviceName, device_id: deviceId })
    });
    const data = await res.json();
    if (data.token) {
      this.setAuthToken(data.token);
    }
    return data;
  }

  async pairWithQR(qrPayload: string, deviceId: string = "mobile-qr-client") {
    const res = await this.fetchWithTimeout(`${this.baseUrl}/api/v1/mobile/pair/qr/scan`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ qr_payload: qrPayload, device_id: deviceId })
    });
    const data = await res.json();
    if (data.access_token || data.token) {
      this.setAuthToken(data.access_token || data.token);
    }
    return data;
  }

  async fetchTrustedDevices() {
    const res = await this.fetchWithTimeout(`${this.baseUrl}/api/v1/mobile/devices`, {
      headers: this.getHeaders()
    });
    return res.json();
  }

  async fetchTelemetry(): Promise<SystemTelemetryData> {
    const res = await this.fetchWithTimeout(`${this.baseUrl}/api/v1/mobile/telemetry`, {
      headers: this.getHeaders()
    });
    return res.json();
  }

  async sendRemoteCommand(command: string, params: Record<string, any> = {}) {
    const res = await this.fetchWithTimeout(`${this.baseUrl}/api/v1/mobile/system/command`, {
      method: "POST",
      headers: this.getHeaders(),
      body: JSON.stringify({ command, params })
    });
    return res.json();
  }

  async submitApprovalDecision(
    approvalId: string,
    decision: 'approve' | 'deny' | 'always_allow' | 'always_deny',
    biometricAuthenticated: boolean = false,
    biometricSignature?: string,
    challenge?: string,
    deviceId?: string
  ) {
    const res = await this.fetchWithTimeout(`${this.baseUrl}/api/v1/mobile/approvals/respond`, {
      method: "POST",
      headers: this.getHeaders(),
      body: JSON.stringify({
        approval_id: approvalId,
        decision,
        challenge: challenge || undefined,
        device_id: deviceId || undefined,
        biometric_authenticated: biometricAuthenticated,
        biometric_signature: biometricSignature || undefined
      })
    });
    return res.json();
  }

  async getScreenPreview() {
    const res = await this.fetchWithTimeout(`${this.baseUrl}/api/v1/mobile/screen/preview`, {
      headers: this.getHeaders()
    });
    return res.json();
  }

  async searchFiles(query: string) {
    const res = await this.fetchWithTimeout(`${this.baseUrl}/api/v1/mobile/files/search?query=${encodeURIComponent(query)}`, {
      headers: this.getHeaders()
    });
    return res.json();
  }

  async toggleLiveMode(enable: boolean) {
    const res = await this.fetchWithTimeout(`${this.baseUrl}/api/v1/mobile/live_mode/toggle?enable=${enable}`, {
      method: "POST",
      headers: this.getHeaders()
    });
    return res.json();
  }

  async fetchLiveModeStatus(): Promise<LiveModeStatusResponse> {
    const res = await this.fetchWithTimeout(`${this.baseUrl}/api/v1/mobile/live_mode/status`, {
      headers: this.getHeaders()
    });
    return res.json();
  }

  async fetchConversations(limit: number = 30): Promise<{ status: string; conversations: ConversationListItem[] }> {
    const res = await this.fetchWithTimeout(`${this.baseUrl}/api/conversations?limit=${limit}`, {
      headers: this.getHeaders()
    });
    return res.json();
  }

  async fetchConversationById(id: number | string): Promise<{ status: string; conversation?: ConversationDetail }> {
    const res = await this.fetchWithTimeout(`${this.baseUrl}/api/conversations/${id}`, {
      headers: this.getHeaders()
    });
    return res.json();
  }

  async fetchChatHistory() {
    return this.fetchConversations();
  }

  async fetchRegisteredTools(): Promise<{ status: string; count: number; tools: Array<Record<string, any>> }> {
    const res = await this.fetchWithTimeout(`${this.baseUrl}/api/v1/tools`, {
      headers: this.getHeaders()
    });
    return res.json();
  }

  async executeTool(toolName: string, args: Record<string, any> = {}) {
    return this.sendRemoteCommand(toolName, args);
  }

  async sendNaturalLanguageCommand(prompt: string, conversationId?: number | string | null) {
    const payload: Record<string, any> = { text: prompt, message: prompt };
    if (conversationId) {
      payload["conversation_id"] = conversationId;
    }
    const res = await this.fetchWithTimeout(`${this.baseUrl}/api/v1/chat`, {
      method: "POST",
      headers: this.getHeaders(),
      body: JSON.stringify(payload)
    });
    return res.json();
  }

  async fetchDiagnostics() {
    const res = await this.fetchWithTimeout(`${this.baseUrl}/api/v1/mobile/diagnostics`, {
      headers: this.getHeaders()
    });
    return res.json();
  }

  async fetchBrainMemories() {
    const res = await this.fetchWithTimeout(`${this.baseUrl}/api/v1/mobile/brain/memory`, {
      headers: this.getHeaders()
    });
    return res.json();
  }

  connectWebSocket(
    onTelemetry: (data: SystemTelemetryData) => void,
    onMessage: (msg: any) => void,
    onStatusChange?: (connected: boolean) => void
  ) {
    const mgr = this.getConnectionManager();

    if (onStatusChange) {
      mgr.subscribeState((state) => {
        onStatusChange(state === 'connected');
      });
    }

    mgr.subscribeMessage((msg: any) => {
      try {
        if (msg && msg.type === "telemetry" && msg.data) {
          onTelemetry(msg.data);
        } else {
          onMessage(msg);
        }
      } catch (err) {
        console.error("[JarvisMobile] Error in message callback:", err);
      }
    });

    if (!mgr.isConnected()) {
      mgr.connect();
    }
  }

  disconnectWebSocket() {
    if (this.connectionManager) {
      this.connectionManager.disconnect();
    }
    if (this.ws) {
      try {
        this.ws.close();
      } catch {}
      this.ws = null;
    }
  }

  async fetchPendingApprovals() {
    const res = await this.fetchWithTimeout(`${this.baseUrl}/api/v1/mobile/approvals/pending`, {
      headers: this.getHeaders()
    });
    return res.json();
  }

  sendAudioInput(audioBase64: string) {
    this.sendWebSocketMessage({ type: "audio", audio_base64: audioBase64 });
  }

  sendChatMessage(text: string) {
    this.sendWebSocketMessage({ type: "chat", text, query: text });
  }

  sendWebSocketMessage(msg: any) {
    const mgr = this.getConnectionManager();
    if (mgr.isConnected()) {
      mgr.sendMessage(msg);
    } else if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(msg));
    }
  }

  // ── PART A: FCM PUSH NOTIFICATION REGISTRATION ─────────────────────
  async registerFCMToken(fcmToken: string, deviceId: string = "android-companion-1", deviceName: string = "Android Phone") {
    try {
      const res = await fetch(`${this.baseUrl}/api/v1/mobile/fcm/register_token`, {
        method: "POST",
        headers: this.getHeaders(),
        body: JSON.stringify({
          device_id: deviceId,
          fcm_token: fcmToken,
          platform: "android",
          device_name: deviceName
        })
      });
      return await res.json();
    } catch (e) {
      console.error("Failed to register FCM token:", e);
      return { status: "error", error: String(e) };
    }
  }

  // ── PART B: WEBRTC FULL-DUPLEX SIGNALLING ───────────────────────────
  async initiateWebRTCSession(sessionId: string = "webrtc_session_1", localSdpOffer: string = "") {
    try {
      const res = await fetch(`${this.baseUrl}/api/v1/mobile/webrtc/offer`, {
        method: "POST",
        headers: this.getHeaders(),
        body: JSON.stringify({
          session_id: sessionId,
          sdp: localSdpOffer || "v=0\r\no=- 123 2 IN IP4 127.0.0.1\r\ns=Mobile Mic Stream\r\nm=audio 9 UDP/TLS/RTP/SAVPF 111\r\n",
          peer_id: "android-companion-1"
        })
      });
      return await res.json();
    } catch (e) {
      console.error("WebRTC offer initiation error:", e);
      return { status: "error", error: String(e) };
    }
  }

  // ── PART C: GPS GEOFENCING BACKGROUND UPDATE ───────────────────────
  async sendGPSLocationUpdate(latitude: number, longitude: number, accuracy: number = 10.0, deviceId: string = "android-companion-1") {
    try {
      const res = await fetch(`${this.baseUrl}/api/v1/mobile/geofence/update_location`, {
        method: "POST",
        headers: this.getHeaders(),
        body: JSON.stringify({
          device_id: deviceId,
          latitude,
          longitude,
          accuracy
        })
      });
      return await res.json();
    } catch (e) {
      console.error("GPS location update failed:", e);
      return { status: "error", error: String(e) };
    }
  }

  // ── PART D: ADVANCED GOAL RECOVERY & OAUTH STATUS ──────────────────
  async recoverInterruptedGoals() {

    try {
      const res = await fetch(`${this.baseUrl}/api/v1/developer/recover_interrupted_goals`, {
        method: "POST",
        headers: this.getHeaders()
      });
      return await res.json();
    } catch (e) {
      return { status: "error", message: String(e) };
    }
  }

  async fetchOAuthStatus() {
    try {
      const res = await fetch(`${this.baseUrl}/api/v1/oauth/status`, {
        headers: this.getHeaders()
      });
      return await res.json();
    } catch (e) {
      return { status: "error", error: String(e) };
    }
  }

  // ── PART E: mDNS LAN AUTO-DISCOVERY PROBE ───────────────────────────
  async autoDiscoverServer(knownCandidates: string[] = []): Promise<{ host: string; port: number } | null> {
    const candidates = Array.from(new Set([
      this.serverHost,
      ...knownCandidates,
      "10.0.2.2",
      "127.0.0.1",
      "localhost"
    ])).filter(Boolean);

    for (const host of candidates) {
      try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 1200);
        const res = await fetch(`http://${host}:${this.serverPort}/api/v1/mobile/status`, {
          signal: controller.signal
        });
        clearTimeout(timeoutId);
        if (res.ok) {
          this.setServerAddress(host, this.serverPort);
          return { host, port: this.serverPort };
        }
      } catch {
        // Continue probing next LAN candidate
      }
    }
    return null;
  }
}

export const mobileClient = new JarvisMobileClient();


