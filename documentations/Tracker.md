# 📋 Project Capability Directory & System Roadmap

This document outlines the capabilities, completed features, active work, and upcoming roadmap of the **JARVIS Personal AI Operating System**. **Last Updated:** July 29, 2026

---

## 1. Complete Capability Directory

### 1.1. Production Asset-Based 3D Face Avatar Engine & UI Architecture
* **Asset-Based 3D Head Engine**: Pre-modeled 3D humanoid head asset loaded via Three.js `GLTFLoader` (`GltfHeadLoader.ts`) with metallic-roughness PBR skin shading, smooth organic cranium curves, and sculpted 3D ears. Zero primitive box/sphere shapes.
* **Viseme Speech Lip-Sync**: Real-time TTS audio amplitude viseme mapping (`viseme_aa`, `viseme_E`, `viseme_O`, `jawOpen`) driven by Web Audio API `AnalyserNode`.
* **Natural 60 FPS Idle Motion & Double-Blinking**: 60 FPS chest/neck breathing sway, micro eye gaze shifts, and randomized double-blinking (`NaturalIdleAnimator.ts`).
* **Interactive 3D Rotation Toggle**: Interactive HUD button (`ROTATE: ON` / `ROTATE: OFF`) allowing users to freeze or resume continuous 360-degree rotation instantly.
* **Header Dropdown & 70/30 Resizable Splitter**: Consolidated header navigation dropdown (`☰ Command Center ▾`) with **Chat History** session log, and draggable vertical divider bar with `localStorage` split ratio persistence (`jarvis_split_ratio`).

### 1.2. Unified AI OS Architecture & Central Desktop World Model
* **Unified Execution Pipeline (`UnifiedPipeline`)**: Enforces a single 10-step lifecycle for every request across all entry points: `User Request → Intent → Planner → Tool Selection → Execute → Observe → Reflection → Learning → Strategy Update → Save Experience`.
* **Central Desktop World Model (`WorldModel`)**: Single source of truth tracking spatial monitor topologies, foreground window title, process ID, native Win32 UIA control tree, browser tab title, and Windows clipboard state.
* **Unified Tool Registry (`ToolRegistry`)**: Decouples task planning from concrete service implementations with parameter schemas and risk audits (`low`, `medium`, `high`).
* **Hybrid Perception Cascade**: Multi-tiered perception for Live Mode (1. Win32 UIA → 2. Accessibility APIs → 3. Win32 APIs → 4. Vision AI → 5. OCR).

### 1.3. Self-Improving Personal AI Operating System Core
* **Experience Engine (`ExperienceEngineService`)**: Records every user goal, tool used, execution steps, duration, result, success/failure boolean, confidence score, failure cause, and recovery method into SQLite `data/experiences.db` (WAL mode).
* **Reflection Engine (`ReflectionEngineService`)**: Evaluates completed operations to determine why a task succeeded/failed, whether a faster or safer approach exists, and whether the procedure should become a permanent preferred strategy stored in `HybridMemorySystem`.
* **Self-Healing Engine (`SelfHealingEngine`)**: Automatically diagnoses runtime failures (executable moved, missing file, UI selector changed, element moved, network error) and executes recovery cascades (PATH scan -> Win32 UIA -> Screen OCR -> Mobile Gatekeeper) without repeating past mistakes.
* **Strategy Memory & Dynamic Confidence System (`StrategyMemoryService`)**: Stores procedural execution strategies ranked by dynamic confidence scores (Win32 UIA: 95%, Playwright: 92%, OCR: 70%, Pixel: 40%).

### 1.4. Android Mobile Companion & Mission Control System
* **8-Tab Mission Control Interface**: Full Material 3 responsive dark-mode dashboard inside [`companion.html`](file:///c:/Users/ashri/JARVIS/mobile_app/android/app/src/main/assets/companion.html) embedded within the Native Android APK.
  - **Tab 1: Telemetry & Hardware**: Live CPU %, RAM %, GPU %, Disk %, Battery %, and active task metrics.
  - **Tab 2: AI Live Chat**: Push-to-talk voice dictation and parallel mobile speech output.
  - **Tab 3: Approval Gatekeeper**: Intercept dangerous desktop operations (shutdown, file delete, terminal execute) with mobile approval buttons.
  - **Tab 4: Screen & Apps**: Desktop screenshot preview and application switcher/killer.
  - **Tab 5: Task Queue**: Inspect pending, running, and completed tasks.
  - **Tab 6: File Indexer**: Sub-second file search via SQLite FTS5 indexer.
  - **Tab 7: Brain & Memory**: Interactive Knowledge Graph visualizer and operational modes.
  - **Tab 8: Self-Diagnostics**: System health check across all OS services.

---

## 2. Completed Milestones

- [x] Production Asset-Based 3D Head Engine (`GLTFLoader` with PBR skin shading)
- [x] Speech Viseme Lip-Sync & Natural Idle Breathing/Blinking Animator
- [x] Interactive 3D ROTATION ON / OFF Toggle Button
- [x] Header Navigation Dropdown Consolidation (`☰ Command Center ▾`) & Chat History Session Log
- [x] Resizable 70/30 Panel Splitter Engine with `localStorage` Persistence
- [x] Iconic JARVIS Cyan Blue Theme Restoration (`#00e5ff`)
- [x] Dedicated Android Native WebView Companion Shell & 8-Tab Mission Control
- [x] Mobile Approval Center & Security Gatekeeper Intercept
- [x] Dedicated Live Mode Core (AI Screen Assistant) & Win32 UIA Perception
- [x] Self-Improving OS Engine (Experience, Reflection, Self-Healing, Strategy Memory)
- [x] Offline GGML Speech Recognition & Low-Latency 4-Bit GGUF Quantization
- [x] Multi-Device Peer-to-Peer Mesh Syncing (`SyncService`)
- [x] Biometric Face & Voice Speaker Verification Engine
- [x] Real 128-d Face-Identity Security Lock Screen (`FaceBiometricsService` & `FaceLockScreen.tsx`)
- [x] Full MCU J.A.R.V.I.S. 21 Micro-Agent Ecosystem Architecture (`BaseMicroAgent` & `mcu_agents.py`)
- [x] Marvel J.A.R.V.I.S. Situational Personality Engine (`PersonalityEngine`)
- [x] Real EventBus Subscriber Integration (`WorldModel` bound to `task.*`, `config_reloaded`, `security.approval_required`)
- [x] Standalone Background Hardware Microphone Listener for Wake Word Detection (`WakeWordService`)
- [x] Full Live Mode AI Assistant Experience (Phases 0 - 3: Toggle Fix, Goal Persistence, Spotlight Overlay, Win32 `SetWindowPos` `resize_window`)

---

## 3. Future TODO Roadmap (7–13)

### 7: Autonomous Agent Ecosystem
- [ ] **Multi-Agent Orchestration & Delegation**: Sub-agent spawning (`CodeAgent`, `ResearchAgent`, `SecurityAgent`) in isolated threads with IPC message bus.
- [ ] **Long-Horizon Task Continuity**: Persistent goal queue with multi-day checkpointing and KV-cache pruning.

### 8: Predictive & Proactive Intelligence
- [ ] **Habit Learning & Predictive Automation**: Behavioral pattern mining to pre-stage workspaces before user commands.
- [ ] **Ambient Multi-Modal Presence**: Bluetooth RSSI proximity lock/unlock and eye gaze tracking.

### 9: External Ecosystem Integration
- [ ] **Universal API Connector Vault**: OAuth2 refresh token manager for 100+ services.
- [ ] **Smart Home & IoT Bridge**: Matter/Thread protocol local device control and Home Assistant MQTT sync.
