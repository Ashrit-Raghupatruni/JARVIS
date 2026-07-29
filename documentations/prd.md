# 🤖 Product Requirements Document (PRD) — JARVIS Personal AI Operating System

## 1. Executive Summary & Vision

JARVIS is a **Personal AI Operating System** designed for single-user deployment across **1 Windows Laptop (Brain) + 1 Dedicated Android Phone (Companion HUD)**. Inspired by Iron Man's home computer assistant, JARVIS acts as an autonomous digital companion bridging human speech with Windows OS operations, application control, and mobile remote monitoring. **Last Updated:** July 29, 2026

Unlike commercial cloud SaaS platforms, JARVIS is **100% local-first, privacy-focused, free of hosting fees**, and optimized for sub-millisecond local execution with dynamic cloud AI fallback when high reasoning capabilities are needed.

---

## 2. Target Device Topology & Core Specs

```
┌───────────────────────────────────────┐         ┌───────────────────────────────────────┐
│          PRIMARY WINDOWS LAPTOP       │         │        DEDICATED ANDROID PHONE        │
│ - FastAPI Monolith Engine (Port 8000) │◄───────►│ - Material 3 Mobile Companion App     │
│ - Electron Desktop Shell (3D Orb HUD) │   LAN   │ - Mobile Security Approval Gatekeeper │
│ - SQLite WAL + ChromaDB Knowledge Hub │   WS    │ - Remote Voice & Telemetry Dashboard  │
└───────────────────────────────────────┘         └───────────────────────────────────────┘
```

---

## 3. Key Product Requirements

### 3.1. Dedicated Android Companion App & Security Gatekeeper
* **One-Time Pairing**: 6-digit numeric PIN & QR code scanning (`/api/v1/mobile/pair`) issuing 1-year signed JWT access tokens saved to `data/trusted_devices.json`.
* **Mobile Security Approval System (Gatekeeper)**:
  - Dangerous actions (file deletions, terminal commands, system restarts, registry updates) pause desktop execution and send instant mobile notifications.
  - Interactive approval choices: `[ ✅ Approve ]`, `[ ❌ Deny ]`, `[ 🛡️ Always Allow ]`, `[ ⛔ Always Deny ]`, `[ ⏱️ Auto-Timeout (30s) ]`.
* **Real-time Hardware Telemetry HUD**: Material 3 live metric cards for CPU %, RAM %, GPU %, battery, active task, and AI provider.
* **Remote Desktop Commands**: 1-tap `Shutdown`, `Restart`, `Lock`, `Launch App`, `Pause AI`, `Cancel Task`.
* **On-Demand Screen Snapshot Preview**: Non-continuous privacy-first screen previews with touch annotation capabilities.

### 3.2. Native Windows UI Automation, File Search & High-Precision Structured OCR
* **Resolution-Independent UI Control**: Native Win32 Accessibility UI Automation (`UIAEngine`) for locating buttons and text fields by title, control type, or automation ID without pixel coordinate drift.
* **Sub-second Natural Language File Indexing**: SQLite FTS5 indexer (`FileIndexerService`) for searching local workspace documents and code.
* **High-Precision Structured Layout & Table OCR Engine**: Deep vision PP-StructureV3 table, layout, and bounding box text extraction in `VisionService` with pytesseract and PIL grid fallback.

### 3.3. Asset-Based 3D Face Avatar Engine & UI Dropdown Consolidation
* **Asset-Based 3D Head Engine**: Pre-modeled 3D humanoid head asset loaded via Three.js `GLTFLoader` with metallic-roughness PBR skin shading, smooth organic cranium curves, and sculpted 3D ears. Zero primitive box/sphere shapes.
* **Viseme Speech Lip-Sync & Natural Idle Animator**: Speech viseme mapping (`viseme_aa`, `viseme_E`, `viseme_O`, `jawOpen`) driven by Web Audio TTS amplitude and 60 FPS continuous natural breathing/blinking cycles.
* **3D ROTATION ON / OFF Toggle**: Interactive HUD button (`ROTATE: ON` / `ROTATE: OFF`) allowing users to freeze or resume continuous 360-degree rotation.
* **Header Dropdown & 70/30 Resizable Splitter**: Consolidated header navigation dropdown (`☰ Command Center ▾`) with **Chat History** session log, and draggable vertical divider bar with `localStorage` split ratio persistence.

### 3.4. Autonomous Web Agent Loop & Proactive Intelligence
* **Autonomous Web Agent Loop**: Perceive-decide-act-observe agent loop (`run_browser_agent` in `BrowserService`) combining Playwright DOM element indexing with spoken tool invocation (`browser_agent_task`).
* **Proactive Desktop Intelligence Suite**: Instant TTS barge-in cancellation (`cancel_playback`), exponential backoff retry decorator, 3.0s vision rate-limiter, Windows Registry boot auto-start (`system_autostart.py`), Clipboard Quick-Action Intelligence (`clipboard_intelligence.py`), session memory continuity (`session_memory.json`), content-safe topic watcher, and Proactive 2.0 with a 20-minute interjection cooldown.

### 3.5. Self-Improving Personal AI Operating System Architecture
* **Experience Engine (`ExperienceEngineService`)**: Records every action goal, tool used, execution steps, duration, result, success/failure boolean, confidence score, failure cause, and recovery method into SQLite `data/experiences.db` (WAL mode).
* **Reflection Engine (`ReflectionEngineService`)**: Post-task evaluator assessing *Did it succeed/fail? Why? What could have been better, faster, or safer? Should this become the preferred strategy?*
* **Self-Healing Engine (`SelfHealingEngine`)**: Automatically diagnoses runtime failures (executable moved, missing file, UI selector changed, element moved, network error) and executes recovery cascades (PATH scan -> Win32 UIA -> Screen OCR -> Mobile Gatekeeper) without repeating past mistakes.
* **Strategy Memory & Dynamic Confidence System (`StrategyMemoryService`)**: Ranks procedural strategies by dynamic confidence scores (Win32 UIA: 95%, Playwright: 92%, OCR: 70%, Pixel: 40%).

### 3.6. Next-Gen Upgrades & Live Mode Core (100% Completed)
- [x] **Offline Speech Recognition & Low-Latency LLM Quantization**: Upgraded STT with offline GGML `faster-whisper` and 4-bit GGUF quantization for local `PrashEngine` LLM inference (`backend/prash/engine.py`).
- [x] **Multi-Device Peer-to-Peer Mesh Syncing**: Encrypted UDP broadcast P2P discovery & Fernet datachannel mesh syncing between desktop, phone, tablet, and smart wearables (`backend/services/sync_service.py`).
- [x] **Autonomous Workflow Learning & Macro Recording**: Desktop UI interaction recorder & automated Python macro script synthesizer (`backend/services/autonomous_engine.py`).
- [x] **Biometric Face & Voice Speaker Verification**: Local speaker embedding identification via cosine distance vector similarity and facial recognition camera login (`backend/services/voice_intelligence.py`).
- [x] **Edge RAG Knowledge Graph Visualizer**: Interactive NetworkX 3D graph visualization of long-term memories in `HybridMemorySystem` rendered inside Electron and Mobile Mission Control (`backend/services/hybrid_memory_system.py`).
- [x] **Dedicated Live Mode (AI Screen Assistant)**: Real-time continuous desktop observation mode with sub-30ms Win32 UIA Scene Graph extraction, 1.0 FPS perception loop, step-by-step guidance, smart form auto-fill with pre-submission regex validation, and multi-monitor workspace layout restorer (`backend/services/live_mode/`).
- [x] **Asset-Based 3D Face Avatar & Viseme Engine**: Production GLTF 3D head loader with speech visemes, PBR skin shaders, 85mm portrait camera optics, and 3D ROTATION ON/OFF toggle.

---

## 4. Future Product Architecture Roadmap (7–13)

### 7: Autonomous Agent Ecosystem
* **Multi-Agent Orchestration & Delegation**: Sub-agent spawning (`CodeAgent`, `ResearchAgent`, `SecurityAgent`) in isolated threads with IPC message bus and hierarchical 100-step planning.
* **Long-Horizon Task Continuity**: Persistent goal queue with multi-day checkpointing, context compression engine (KV-cache pruning + semantic chunking), and cross-session state restoration.

### 8: Predictive & Proactive Intelligence
* **Habit Learning & Predictive Automation**: Behavioral pattern mining (routine pre-staging), anomaly detection (CPU spikes, unknown USB devices), and context-aware intent prediction.
* **Ambient Intelligence Layer**: Facial recognition + Bluetooth presence detection (auto-lock/unlock), eye gaze attention tracking, and emotion-aware voice/text response tuning.

### 9: External Ecosystem Integration
* **Universal API Connector Framework**: Encrypted OAuth2 token vault for 100+ services (Gmail, Slack, Notion, GitHub, AWS), NL API builder, and webhook listener server.
* **Smart Home & IoT Bridge**: Matter/Thread protocol local device control, Home Assistant bidirectional sync, and mobile GPS geofencing automation.

### 10: Security & Privacy Hardening
* **Zero-Trust Security Architecture**: Homomorphic encryption for RAG queries (TenSEAL), TPM/Secure Enclave key storage, and continuous behavioral biometrics (typing/mouse patterns).
* **Federated Learning Node**: Local LoRA adapter fine-tuning on user data with differential privacy noise injection.

### 11: Advanced Interaction Modes
* **Spatial Computing Integration**: Vision Pro / Quest AR passthrough overlay, hand tracking 2.0 pinch/grab file manipulation, and spatial virtual multi-monitors.
* **Collaborative Multi-User Mode**: Voice-based user profile switching with isolated memory spaces, shared knowledge hubs, and multi-user conflict resolution.

### 12: Performance & Optimization
* **Hardware Acceleration Expansion**: NVIDIA TensorRT / AMD MIGraphX inference pipelines, NPU offloading (Intel AI Boost / Apple Neural Engine / Qualcomm Hexagon), and custom CUDA kernels.
* **Edge Distributed Computing**: LAN cluster layer distribution (combining laptop + desktop + phone VRAM) and cost-aware cloud burst offloading.

### 13: Developer & Extensibility Platform
* **Plugin Architecture 2.0**: WASM sandboxed third-party plugins, visual drag-and-drop workflow builder (n8n/Node-RED style), and curated plugin marketplace.
* **Custom Model Training Pipeline**: Synthetic dataset generator, Int4/Int8 quantization auto-tuner, and dynamic LoRA model merger at runtime.
