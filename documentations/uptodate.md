# JARVIS — Comprehensive Status, Tech Stack, & Features Overview

This document serves as the single source of truth for JARVIS's current capabilities, system architecture, tech stack, and development status. **Last Updated:** July 25, 2026

---

## 📊 Development Roadmap & Gantt Chart

```mermaid
gantt
    title JARVIS Development Roadmap
    dateFormat YYYY-MM-DD
    section Core Foundation
    Backend WebSocket REST Server :done, t1_1, 2026-06-01, 15d
    SQLite Async SQLAlchemy Integration :done, t1_2, 2026-06-10, 10d
    section Speech and Automation
    STT Whisper and TTS EdgeTTS :done, t2_1, 2026-06-20, 12d
    Wake Word and Double Clap services :done, t2_2, 2026-07-01, 8d
    UI Automation and Playwright agents :done, t2_3, 2026-07-05, 10d
    section Visual and UX
    Electron Shell and React 19 UI :done, t3_1, 2026-07-08, 6d
    3D ThreeJS Orb and Hand Gestures :done, t3_2, 2026-07-10, 5d
    section Local AI Orchestration
    Prash Local AI Engine and Tokenizer :done, t4_1, 2026-07-12, 8d
    LangGraph Tool Orchestration Loop :done, t4_2, 2026-07-15, 6d
    section Mobile Mission Control
    Native Android Shell and WebSockets :done, t5_1, 2026-07-18, 5d
    8 Tab Mission Control UI and Approval Gatekeeper :done, t5_2, 2026-07-20, 4d
    Parallel Mobile Voice and Desktop Shutdown Approval :done, t5_3, 2026-07-22, 2d
    section Next-Gen AI OS Core
    Offline GGML Speech and 4Bit GGUF Quantization :done, t6_1, 2026-07-23, 1d
    Multi Device Peer to Peer Mesh Syncing :done, t6_2, 2026-07-23, 1d
    Autonomous Macro Recording and Script Synthesis :done, t6_3, 2026-07-23, 1d
    Biometric Speaker and Facial Verification :done, t6_4, 2026-07-23, 1d
    Edge RAG Interactive 3D Knowledge Graph Visualizer :done, t6_5, 2026-07-23, 1d
    Experience Engine Action Tracing and SQLite WAL Storage :done, t6_6, 2026-07-23, 1d
    Reflection Engine Post Task Self Evaluation :done, t6_7, 2026-07-23, 1d
    Self Healing Engine and Fault Recovery Cascade :done, t6_8, 2026-07-23, 1d
    Procedural Strategy Memory and Dynamic Confidence System :done, t6_9, 2026-07-23, 1d
    System Operational Modes Coding Gaming Work Research :done, t6_10, 2026-07-23, 1d
    Live Mode 2.0 Event Driven Real Time Collaborator :done, t6_11, 2026-07-24, 1d
    Unified 10-Step Self-Improving OS Lifecycle Pipeline :done, t6_12, 2026-07-24, 1d
    section Autonomous Agent Ecosystem
    Multi Agent Orchestration and Sub Agent Delegation :active, t7_1, 2026-07-25, 5d
    Long Horizon Task Continuity and Context Compression :t7_2, 2026-07-30, 5d
    section Predictive Intelligence
    Habit Learning and Behavioral Pattern Mining :t8_1, 2026-08-04, 5d
    Ambient Intelligence and Presence Attention Tracking :t8_2, 2026-08-09, 5d
    section External Ecosystem
    Universal API Connector Framework and Token Vault :t9_1, 2026-08-14, 5d
    Smart Home and IoT Bridge Matter HA Geofencing :t9_2, 2026-08-19, 5d
    section Security and Privacy
    Zero Trust Security and Homomorphic RAG Encryption :t10_1, 2026-08-24, 5d
    Federated Learning Node and Local LoRA Fine Tuning :t10_2, 2026-08-29, 5d
    section Advanced Interaction
    Spatial Computing Integration AR Passthrough :t11_1, 2026-09-03, 5d
    Collaborative Multi User Mode and Shared Knowledge :t11_2, 2026-09-08, 5d
    section Performance and Optimization
    Hardware Acceleration TensorRT NPU Offloading :t12_1, 2026-09-13, 5d
    Edge Distributed Computing and LAN Cluster VRAM :t12_2, 2026-09-18, 5d
    section Developer Platform
    Plugin Architecture 2.0 WASM Sandbox and Visual Builder :t13_1, 2026-09-23, 5d
    Custom Model Training Pipeline and Quant Auto Tuner :t13_2, 2026-09-28, 5d
```

---

## 📋 Tech Stack

The architecture is split into a **React + Electron** desktop client (frontend), a **FastAPI + WebSockets** backend service (Python), and a **Dedicated Native Android Mobile Companion App** (Native Android Java/WebView + HTML5/JS).

### Desktop Client (Frontend Shell)
* **Shell/Container:** Electron v35.0.0 (manages OS-level desktop windows, system tray, global shortcut registration)
* **Framework:** React v19.1.0 + TypeScript v5.8.0 + Vite v6.4.2
* **Build System:** `electron-vite` v3.1.0 + `electron-builder` v25.1.0
* **Styling:** Tailwind CSS v4.1.0 + `@tailwindcss/vite`
* **State Management:** Zustand v5.0.0
* **3D Visuals:** Three.js v0.185.1 (WebGL rendering of a procedural 3D Arc Reactor focal core with battery-saver visibility listener)

## 2. Capability Directory

### 2.0. Unified AI OS Architecture & World Model
* **Unified Execution Pipeline (`UnifiedPipeline`)**: Single 10-step lifecycle for every request across all entry points: `User Request → Intent → Planner → Tool Selection → Execute → Observe → Reflection → Learning → Strategy Update → Save Experience`.
* **Central Desktop World Model (`WorldModel`)**: Single source of truth tracking spatial monitor topologies, foreground window title, process ID, native Win32 UIA control tree, browser tab title, and Windows clipboard state.
* **Unified Tool Registry (`ToolRegistry`)**: Decouples task planning from concrete service implementations with parameter schemas and risk audits (`low`, `medium`, `high`).

### 2.1. Live Mode (AI Screen Assistant) & Native Perception Core

### Mobile Mission Control App (Native Android Companion)
* **Project Folder:** [`mobile_app/android/`](file:///c:/Users/ashri/JARVIS/mobile_app/android/)
* **Shell:** Native Android Java Activity (`MainActivity.java`) + WebSettings (`setAllowUniversalAccessFromFileURLs`) + Android Network Security Config (`network_security_config.xml`).
* **UI Interface:** 8-Tab Material 3 Dark Glassmorphism Interface ([`companion.html`](file:///c:/Users/ashri/JARVIS/mobile_app/android/app/src/main/assets/companion.html)).
* **Features:**
  - 📊 **Tab 1: Mission Control & Telemetry**: CPU, RAM, GPU, Disk, Battery, Temp, Active Task, LLM Provider, On-Demand Refresh Stats.
  - 💬 **Tab 2: Live Chat & Voice**: Token streaming, Markdown, Pinned Messages, Push-to-Talk Voice Dictation, **Parallel Mobile Voice Speech Synthesis**, and **Native Push Notifications**.
  - 🛡️ **Tab 3: Mobile Approval Center**: Real-time Security Gatekeeper intercept for dangerous desktop operations and Desktop Shutdown Approval.
  - 🖥️ **Tab 4: Screen & App Control**: Live screen snapshot thumbnail preview, desktop process manager (list, launch, kill).
  - ⚙️ **Tab 5: Task Queue & Workflows**: Real-time task queue monitor (pending, running, completed tasks).
  - 📁 **Tab 6: File Manager**: Sub-second natural language file search via SQLite FTS5 indexer.
  - 🧠 **Tab 7: Brain & Memory**: Long-term memory graph inspection & research citations.
  - 🩺 **Tab 8: Self-Diagnostics**: System health check across CPU, RAM, Disk, LLM router, STT/TTS, and RAG.

### Backend Engine (Python Service)
* **Core Web Server:** FastAPI v0.115.9 + Uvicorn v0.34.2 (runs locally bound to `0.0.0.0:8000`).
* **Mobile Companion Gateway Services**:
  - `MobileAuthService` (`backend/services/mobile_auth.py`): 6-digit PIN pairing, Ed25519/RSA keys, trusted device store ([`data/trusted_devices.json`](file:///c:/Users/ashri/JARVIS/data/trusted_devices.json)), and signed JWT access tokens.
  - `MobileGatewayService` (`backend/services/mobile_gateway.py`): Real-time hardware telemetry streaming, dangerous action execution pausing (`asyncio.Event`), and on-demand screenshot thumbnail previews.
  - `mobile_router.py` & `mobile_ws.py`: REST API endpoints and WebSockets (`/api/v1/mobile/ws` and `/api/v1/mobile/ws/stream`).
* **Database (Relational):** SQLite + SQLAlchemy ORM v2.0.41 + `aiosqlite` v0.21.0 (enforced SQLite WAL mode for concurrency).
* **Windows UI Automation Engine:** `UIAEngine` (`backend/services/uia_engine.py`) using native Win32 accessibility selectors for resolution-independent clicks.
* **Natural Language File Indexer:** `FileIndexerService` (`backend/services/file_indexer.py`) utilizing SQLite Full-Text Search (FTS5) for sub-second file search.

---

## 🎯 Verification & Build Confirmation

- **Backend Python Compilation**: `python -m py_compile backend/models/mobile_schemas.py backend/services/mobile_auth.py backend/services/mobile_gateway.py backend/api/mobile_router.py backend/api/mobile_ws.py backend/main.py` → **`0 errors`**.
- **Android APK Build**: `cd mobile_app/android; .\gradlew.bat assembleDebug --no-daemon` → **`BUILD SUCCESSFUL in 31s`**.
- **ADB Streamed Installation**: `adb install -r -t app-debug.apk` → **`Success`**.
- **GitHub Status**: All updates saved locally — **not pushed to GitHub** per user directive.

---

## 🔮 Upcoming & Future TODO Roadmap

- [x] **Workspace Intelligence & Habit Forecaster**: Tracking project context, goals, workflows, and habit predictions (`WorkspaceIntelligenceService`).
- [ ] **Offline Low-Latency LLM Quantization**: Quantize local Prash engine models to 4-bit GGUF for sub-100ms response times.
- [ ] **Multi-Device P2P Sync**: Secure peer-to-peer WebRTC mesh network between desktop and mobile devices.
- [ ] **Autonomous Macro Learning**: Dynamic learning and recording of repetitive desktop tasks into automated execution pipelines.
