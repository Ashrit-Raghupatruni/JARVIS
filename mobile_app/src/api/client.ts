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

export class JarvisMobileClient {
  private serverHost: string;
  private serverPort: number;
  private token: string | null = null;
  private ws: WebSocket | null = null;

  constructor(serverHost = "192.168.1.100", serverPort = 8000) {
    this.serverHost = serverHost;
    this.serverPort = serverPort;
  }

  setServerAddress(host: string, port: number = 8000) {
    this.serverHost = host;
    this.serverPort = port;
  }

  setAuthToken(token: string) {
    this.token = token;
  }

  get baseUrl() {
    return `http://${this.serverHost}:${this.serverPort}`;
  }

  get wsUrl() {
    return `ws://${this.serverHost}:${this.serverPort}/api/v1/mobile/ws/stream`;
  }

  async pairDevice(deviceName: string, deviceId: string, pairingCode: str, session_id: str) {
    const res = await fetch(`${this.baseUrl}/api/v1/mobile/pair/confirm`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        pairing_session_id: session_id,
        pairing_code: pairingCode,
        device_id: deviceId
      })
    });
    return res.json();
  }

  async fetchTelemetry(): Promise<SystemTelemetryData> {
    const res = await fetch(`${this.baseUrl}/api/v1/mobile/telemetry`);
    return res.json();
  }

  async sendRemoteCommand(command: string, params: Record<string, any> = {}) {
    const res = await fetch(`${this.baseUrl}/api/v1/mobile/system/command`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${this.token}`
      },
      body: JSON.stringify({ command, params })
    });
    return res.json();
  }

  async submitApprovalDecision(approvalId: string, decision: 'approve' | 'deny' | 'always_allow' | 'always_deny') {
    const res = await fetch(`${this.baseUrl}/api/v1/mobile/approvals/respond`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${this.token}`
      },
      body: JSON.stringify({ approval_id: approvalId, decision })
    });
    return res.json();
  }

  async getScreenPreview() {
    const res = await fetch(`${this.baseUrl}/api/v1/mobile/screen/preview`);
    return res.json();
  }

  async searchFiles(query: string) {
    const res = await fetch(`${this.baseUrl}/api/v1/mobile/files/search?query=${encodeURIComponent(query)}`);
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

  sendChatMessage(text: string) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: "chat", text }));
    }
  }
}

export const mobileClient = new JarvisMobileClient();
