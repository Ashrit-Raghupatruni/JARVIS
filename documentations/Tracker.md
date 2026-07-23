# 📋 Project Capability Directory & System Roadmap

This document outlines the capabilities, completed features, active work, and upcoming roadmap of the **JARVIS Personal AI Operating System**. **Last Updated:** July 23, 2026

---

## 1. System Development Roadmap & Gantt Chart

```mermaid
gantt
    title JARVIS Development Roadmap
    dateFormat  YYYY-MM-DD
    section Phase 1: Core Foundation
    Backend WebSocket & REST Server :completed, 2026-06-01, 15d
    SQLite Async SQLAlchemy Integration :completed, 2026-06-10, 10d
    section Phase 2: Speech & Automation
    STT (Whisper) & TTS (Edge-TTS) :completed, 2026-06-20, 12d
    Wake Word & Double-Clap services :completed, 2026-07-01, 8d
    pywinauto/Playwright agents :completed, 2026-07-05, 10d
    section Phase 3: Visual & UX
    Electron Shell & React 19 UI :completed, 2026-07-08, 6d
    3D Three.js Orb & Hand Gestures :completed, 2026-07-10, 5d
    section Phase 4: Local AI & Tool Orchestration
    Prash Local AI Engine & Tokenizer :completed, 2026-07-12, 8d
    LangGraph Tool Orchestration Loop :completed, 2026-07-15, 6d
    section Phase 5: Android Mission Control Companion
    Native Android Shell & WebSockets :completed, 2026-07-18, 5d
    8-Tab Mission Control UI & Approval Gatekeeper :completed, 2026-07-20, 4d
    Parallel Mobile Voice & Desktop Shutdown Approval :completed, 2026-07-22, 2d
    section Phase 6: Upcoming & Future Enhancements
    Offline Local Speech Recognition & Low-Latency LLM Quantization :active, 2026-07-24, 10d
    Multi-Device Peer-to-Peer Mesh Syncing :crit, 2026-08-03, 14d
    Autonomous Workflow Learning & Desktop Macro Recording :2026-08-17, 15d
```

---

## 2. Complete Capability Directory

### 2.1. Android Mobile Companion & Mission Control System
* **8-Tab Mission Control Interface**: Full Material 3 responsive dark-mode dashboard inside [`companion.html`](file:///c:/Users/ashri/JARVIS/mobile_app/android/app/src/main/assets/companion.html) embedded within the Native Android APK.
  - **Tab 1: Mission Control & Hardware Telemetry**: Real-time streaming for CPU %, RAM %, GPU VRAM %, Disk %, Battery %, Temperature, active LLM Provider, active workflow, quick action commands, and instant **On-Demand Refresh Telemetry Stats**.
  - **Tab 2: AI Live Chat & Voice Assistant**: Real-time token streaming from `PlannerAgent` and `LLMService`, supporting Markdown responses, conversation search, pinned messages, Push-to-Talk voice dictation via `window.SpeechRecognition`, **Parallel Mobile Voice Speech Synthesis**, and **Native Push Notifications**.
  - **Tab 3: Mobile Approval Center (Security Gatekeeper)**: Live intercept for dangerous operations (desktop OS shutdown, file deletion, terminal commands, registry edits) with `[ Approve ]`, `[ Deny ]`, `[ Always Allow ]`, and `[ Always Deny ]` responses. When JARVIS desktop closes, it automatically prompts your phone for approval!
  - **Tab 4: Desktop Screen Preview & Application Manager**: Live desktop screenshot thumbnail capture via `PIL.ImageGrab` / `pyautogui`, and process application manager (`psutil`) to inspect, launch, focus, and kill desktop apps.
  - **Tab 5: Task Queue & Workflow Monitor**: Real-time inspection of `TaskQueueService` and `AutonomousEngineService` workflows (pending, running, completed, failed tasks).
  - **Tab 6: File Indexer & Transfer**: Search local workspace files indexed sub-second by SQLite FTS5 indexer (`FileIndexerService`), with remote file download/upload endpoints.
  - **Tab 7: Brain & Memory Inspection**: Live visibility into long-term memories from `HybridMemorySystem`, procedural knowledge, and `ResearchAgent` citations.
  - **Tab 8: Self-Diagnostics & Health Check**: Comprehensive diagnostics across CPU, RAM, Disk, Voice, Planner, RAG, Database, and multi-provider LLM Routers (`llm_router.py`).

### 2.2. Security & Communication Protocol
* **Device Pairing & JWT Authentication**: 6-digit numeric PIN handshake (`/api/v1/mobile/pair`) issuing 1-year signed JWT access tokens stored in [`data/trusted_devices.json`](file:///c:/Users/ashri/JARVIS/data/trusted_devices.json).
* **Network Security & Cross-Origin Access**: Configured [`network_security_config.xml`](file:///c:/Users/ashri/JARVIS/mobile_app/android/app/src/main/res/xml/network_security_config.xml) and `setAllowUniversalAccessFromFileURLs(true)` in [`MainActivity.java`](file:///c:/Users/ashri/JARVIS/mobile_app/android/app/src/main/java/com/jarvis/companion/MainActivity.java#L28) allowing local cleartext HTTP/WebSocket connections on Wi-Fi network `0.0.0.0:8000`.
* **CORS Wildcard Configuration**: Configured `allow_origins=["*"]` in [`backend/api/middleware.py`](file:///c:/Users/ashri/JARVIS/backend/api/middleware.py#L22) permitting browser and mobile client cross-origin preflight requests.

### 2.3. Voice & Speech System
* **Wake Word Activation**: Local parsing of "Hey Jarvis" with `openwakeword` (0.35 confidence threshold).
* **Speech Synthesis (TTS)**: Natural voice streaming over WebSocket via `edge-tts`.
* **Speech Recognition (STT)**: High-speed speech transcription via `faster-whisper` with automatic cloud Gemini API fallback.
* **Clap Listener Guard**: Active state check ignoring clap spikes during voice processing/speaking.

### 2.4. Desktop Automation & File Search
* **Native Windows UI Automation**: `UIAEngine` wrapping Win32 accessibility controls to locate and click buttons resolution-independently.
* **Sub-second File Indexer**: `FileIndexerService` utilizing SQLite Full-Text Search (FTS5) for natural language file search.

### 2.5. Storage Concurrency & WebGL Performance
* **SQLite WAL Mode**: Enforced `PRAGMA journal_mode=WAL;` across all DB connections.
* **WebGL Battery Saver**: `visibilitychange` listener in `Orb.tsx` pausing rendering loops when window is hidden.

---

## 3. Completed Milestones

- [x] Dedicated Android Native WebView Companion Shell
- [x] Full Mission Control 8-Tab Interface Integration
- [x] Real-time Hardware & AI Telemetry Streaming
- [x] Mobile Approval Center & Security Gatekeeper Intercept
- [x] Desktop OS Shutdown Gatekeeper Approval Prompt
- [x] Parallel Mobile Voice Speech Response
- [x] Native Push Notification Dispatcher
- [x] Live Desktop Screen Preview & Application Control
- [x] Brain Memory & Task Queue Monitoring
- [x] Self-Diagnostics Engine & LLM Router Integration

---

## 4. Upcoming & Future TODO Roadmap

### Phase 6: Next-Gen Upgrades & Enhancements
- [ ] **Offline Speech Recognition & Low-Latency LLM Quantization**: Upgrade STT with offline GGML whisper.cpp and 4-bit GGUF quantization for local Prash LLM inference (`backend/prash/engine.py`).
- [ ] **Multi-Device Peer-to-Peer Mesh Syncing**: Enable encrypted P2P discovery between desktop, phone, tablet, and smart wearables using libp2p / WebRTC datachannels.
- [ ] **Autonomous Workflow Learning & Macro Recording**: Record desktop UI interactions and automatically synthesize reusable Python macro scripts via `AutonomousEngineService`.
- [ ] **Biometric Face & Voice Speaker Verification**: Integrate local speaker embedding identification (`VoiceIntelligenceService`) and facial recognition camera login.
- [ ] **Edge RAG Knowledge Graph Visualizer**: Interactive 3D graph visualization of long-term memories in `HybridMemorySystem` rendered inside Electron and Mobile Mission Control.
