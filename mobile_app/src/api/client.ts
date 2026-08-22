/**
 * JARVIS Mobile Companion - Network API & WebSocket Client
 */

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

  constructor(serverHost = "192.168.1.100", serverPort = 8000, useSsl = false) {
    this.serverHost = serverHost;
    this.serverPort = serverPort;
    this.useSsl = useSsl;
  }

  setServerAddress(host: string, port: number = 8000, useSsl: boolean = false) {
    this.serverHost = host;
    this.serverPort = port;
    this.useSsl = useSsl;
  }

  setAuthToken(token: string) {
    this.token = token;
  }

  get baseUrl() {
    const scheme = this.useSsl ? "https" : "http";
    return `${scheme}://${this.serverHost}:${this.serverPort}`;
  }

  get wsUrl() {
    const scheme = this.useSsl ? "wss" : "ws";
    return `${scheme}://${this.serverHost}:${this.serverPort}/api/v1/mobile/ws/stream`;
  }

  private getHeaders() {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (this.token) {
      headers["Authorization"] = `Bearer ${this.token}`;
    }
    return headers;
  }

  async pairDevice(deviceName: string, deviceId: string, pairingCode: string, session_id: string) {
    const res = await fetch(`${this.baseUrl}/api/v1/mobile/pair/confirm`, {
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
    const res = await fetch(`${this.baseUrl}/api/v1/mobile/pair`, {
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
    const res = await fetch(`${this.baseUrl}/api/v1/mobile/pair/qr/scan`, {
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
    const res = await fetch(`${this.baseUrl}/api/v1/mobile/devices`, {
      headers: this.getHeaders()
    });
    return res.json();
  }

  async fetchTelemetry(): Promise<SystemTelemetryData> {
    const res = await fetch(`${this.baseUrl}/api/v1/mobile/telemetry`, {
      headers: this.getHeaders()
    });
    return res.json();
  }

  async sendRemoteCommand(command: string, params: Record<string, any> = {}) {
    const res = await fetch(`${this.baseUrl}/api/v1/mobile/system/command`, {
      method: "POST",
      headers: this.getHeaders(),
      body: JSON.stringify({ command, params })
    });
    return res.json();
  }

  async submitApprovalDecision(approvalId: string, decision: 'approve' | 'deny' | 'always_allow' | 'always_deny') {
    const res = await fetch(`${this.baseUrl}/api/v1/mobile/approvals/respond`, {
      method: "POST",
      headers: this.getHeaders(),
      body: JSON.stringify({ approval_id: approvalId, decision })
    });
    return res.json();
  }

  async getScreenPreview() {
    const res = await fetch(`${this.baseUrl}/api/v1/mobile/screen/preview`, {
      headers: this.getHeaders()
    });
    return res.json();
  }

  async searchFiles(query: string) {
    const res = await fetch(`${this.baseUrl}/api/v1/mobile/files/search?query=${encodeURIComponent(query)}`, {
      headers: this.getHeaders()
    });
    return res.json();
  }

  async toggleLiveMode(enable: boolean) {
    const res = await fetch(`${this.baseUrl}/api/v1/mobile/live_mode/toggle?enable=${enable}`, {
      method: "POST",
      headers: this.getHeaders()
    });
    return res.json();
  }

  async fetchLiveModeStatus(): Promise<LiveModeStatusResponse> {
    try {
      const res = await fetch(`${this.baseUrl}/api/live_mode/status`, {
        headers: this.getHeaders()
      });
      if (res.ok) {
        return res.json();
      }
    } catch {
      // Fallback to mobile router endpoint
    }
    const res = await fetch(`${this.baseUrl}/api/v1/mobile/live_mode/status`, {
      headers: this.getHeaders()
    });
    return res.json();
  }

  async fetchConversations(limit: number = 30): Promise<{ status: string; conversations: ConversationListItem[] }> {
    try {
      const res = await fetch(`${this.baseUrl}/api/conversations?limit=${limit}`, {
        headers: this.getHeaders()
      });
      if (res.ok) {
        return res.json();
      }
    } catch {
      // Fallback
    }
    const res = await fetch(`${this.baseUrl}/api/v1/conversations?limit=${limit}`, {
      headers: this.getHeaders()
    });
    return res.json();
  }

  async fetchConversationById(id: number | string): Promise<{ status: string; conversation?: ConversationDetail }> {
    try {
      const res = await fetch(`${this.baseUrl}/api/conversations/${id}`, {
        headers: this.getHeaders()
      });
      if (res.ok) {
        return res.json();
      }
    } catch {
      // Fallback
    }
    const res = await fetch(`${this.baseUrl}/api/v1/conversations/${id}`, {
      headers: this.getHeaders()
    });
    return res.json();
  }

  async fetchChatHistory() {
    return this.fetchConversations();
  }

  async sendNaturalLanguageCommand(prompt: string, conversationId?: number | string | null) {
    const payload: Record<string, any> = { message: prompt };
    if (conversationId) {
      payload["conversation_id"] = conversationId;
    }
    const res = await fetch(`${this.baseUrl}/api/v1/chat`, {
      method: "POST",
      headers: this.getHeaders(),
      body: JSON.stringify(payload)
    });
    return res.json();
  }

  async fetchDiagnostics() {
    const res = await fetch(`${this.baseUrl}/api/v1/mobile/diagnostics`, {
      headers: this.getHeaders()
    });
    return res.json();
  }

  async fetchBrainMemories() {
    const res = await fetch(`${this.baseUrl}/api/v1/mobile/brain/memory`, {
      headers: this.getHeaders()
    });
    return res.json();
  }

  connectWebSocket(onTelemetry: (data: SystemTelemetryData) => void, onMessage: (msg: any) => void) {
    if (this.ws) {
      this.ws.close();
    }
    this.ws = new WebSocket(this.wsUrl);

    this.ws.onopen = () => {
      console.log("[JarvisMobile] Connected to desktop WebSocket");
    };

    this.ws.onmessage = (e) => {
      try {
        const payload = JSON.parse(e.data);
        if (payload.type === "telemetry") {
          onTelemetry(payload.data);
        } else {
          onMessage(payload);
        }
      } catch (err) {
        console.error("Error parsing WS frame:", err);
      }
    };

    this.ws.onclose = () => {
      console.log("[JarvisMobile] Disconnected from WebSocket");
    };
  }

  async fetchPendingApprovals() {
    const res = await fetch(`${this.baseUrl}/api/v1/mobile/approvals/pending`, {
      headers: this.getHeaders()
    });
    return res.json();
  }

  sendAudioInput(audioBase64: string) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: "audio", audio_base64: audioBase64 }));
    }
  }

  sendChatMessage(text: string) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: "chat", text }));
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
}

export const mobileClient = new JarvisMobileClient();

