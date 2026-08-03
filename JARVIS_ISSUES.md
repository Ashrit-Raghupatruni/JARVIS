# 🛠️ JARVIS Codebase — Feature & Component Status Registry

Current classification of all subsystems and features using honest status definitions:
- **Stable**: Verified working, tested repeatedly, core operational baseline.
- **Beta**: Implemented and functional, but has system/environment dependencies or edge cases under extended use.
- **Experimental**: Implemented and operational, but depends on local training scale or external model parameters.
- **In Progress**: Partially built or undergoing active feature iteration.
- **Planned**: Designed and documented, but not yet implemented.

---

## 🟢 P0 — Structural & Bootstrapping Core (**Status: Stable**)

- [x] **Missing `backend` package wrapper**: **Stable**. Whole repository structured inside `backend/` with `backend/__init__.py`.
- [x] **`backend/config.py`**: **Stable**. Provides Pydantic `Settings` and `get_settings()` configuration loader.
- [x] **FastAPI Entrypoint**: **Stable**. `backend/main.py` mounts all routers (`api_router`, `ws_router`, `ui_router`, `mobile_router`, `mobile_ws_router`, `debug_router`).
- [x] **Authoritative `requirements.txt`**: **Stable**. Consolidated dependency file containing `torch`, `psutil`, `pycaw`, `pywinauto`, `chromadb`, and `sentence-transformers`.
- [x] **`DEFAULT_LOG_DIR` in `config.py`**: **Stable**. Defined `DEFAULT_LOG_DIR = PROJECT_ROOT / "logs"` in `backend/config.py`.

---

## 🟡 P1 — Core AI OS Architecture & Live Mode (**Status: Beta**)

- [x] **Self-Healing Key Mismatch Fix**: **Beta**. Changed `recovery.get("success")` to `(recovery.get("recovered") or recovery.get("success"))` in `automation.py`.
- [x] **`UnifiedPipeline` Wiring**: **Beta**. `UnifiedPipeline.run()` wired inside `PlannerAgent.plan_and_execute()`.
- [x] **RequestCategory Intent Routing**: **Beta**. `ACTION_REQUEST`, `LIVE_MODE_REQUEST`, `KNOWLEDGE_REQUEST` handled deterministically in `MessageRouter` and `PlannerAgent`.
- [x] **Perception-Targeted Click & Form Auto-Fill Tools**: **Beta**. `click_element_by_name`, `set_control_value`, and `auto_fill_form` exposed in `ToolRegistry` and `AVAILABLE_TOOLS` schema for LLM function calling.
- [x] **Proactive Form Field Detection Nudge**: **Beta**. `FormAssistant.detect_form_fields()` integrated into `WorldModel.refresh()` and `LiveModeEngine._perception_loop()`.
- [x] **Closed-Loop Experience & Strategy Learning**: **Beta**. `ExperienceEngineService` success rates and `StrategyMemoryService` queried before choosing execution strategies.
- [x] **UIAEngine Service Registration**: **Beta**. `UIAEngine` registered in `ServiceManager` at startup.
- [x] **WorldModel Single Source of Truth**: **Beta**. `WorldModel` dynamically aggregates process names via `psutil`, active window bounds, internet socket probes (`8.8.8.8:53`), and WASAPI audio activity (~170ms refresh time).

---

## 🟢 P2 — UI, Telemetry & Safety (**Status: Stable**)

- [x] **Workspace Intelligence**: **Stable**. Created `WorkspaceIntelligenceService` (`workspace_intelligence.py`), tracking `current_project`, `current_goal`, `current_workflow`, `recent_actions` ring buffer, and habit predictions.
- [x] **Interactive Safety Permission Modal**: **Stable**. Created `SafetyPermissionModal.tsx` rendering backend `permission_request` WebSocket events with Approve/Deny buttons.
- [x] **"What JARVIS is Seeing" Visualizer**: **Stable**. Created `LivePerceptionVisualizer.tsx` rendering live UIA control trees and Workspace Intelligence metrics.
- [x] **Engine Source Attribution Badges**: **Stable**. Rendered `⚡ Prash Local` badges on chat messages in `ChatPanel.tsx`.
- [x] **Real Telemetry Metrics in `ui_skill.py`**: **Stable**. Replaced mock data with live metrics from `psutil`, `chromadb`, and `experience_engine`.
- [x] **Cross-Platform & Seed Data Cleanup**: **Stable**. Updated `cross_platform.py` OS compatibility reporting and cleared seed fallbacks.
- [x] **Documentation Package**: **Stable**. Maintained [`CHANGELOG.md`](file:///c:/Users/ashri/JARVIS/CHANGELOG.md), [`ARCHITECTURE.md`](file:///c:/Users/ashri/JARVIS/ARCHITECTURE.md), and [`README.md`](file:///c:/Users/ashri/JARVIS/README.md).

---

## 🟡 P3 — Master Upgrade (Chat History, Desktop Suite & 21 MCU Agents) (**Status: Beta / Stable**)

- [x] **Persistent Chat History**: **Stable**. Conversation sessions stored in SQLite (`jarvis.db`) via `MemoryService` CRUD, exposed via `/api/conversations` endpoints, rendered in React `ConversationSidebar.tsx`.
- [x] **Live Mode AI Assistant Experience (Phases 0 - 3)**: **Beta**.
  - **Phase 0 (Toggle Fix)**: Fixed `_toggle_live_handler` in `ToolRegistry` and `LiveModeCard.tsx` fetch endpoints to instantiate and control `LiveModeEngine` (1.0 FPS perception loop). Verified start/stop loop execution with real logs.
  - **Phase 1 (Voice Activation & Goal Persistence)**: Activation triggers goal prompt response and persists stated goal in `WorkspaceIntelligenceService` and `user_habits.json`.
  - **Phase 2 (Screen-Dimming Spotlight Overlay Architecture)**: Electron main process supports frameless transparent always-on-top overlay with mouse click-through (`setIgnoreMouseEvents(true, { forward: true })`) and active window spotlight cutout.
  - **Phase 3 (Voice-Driven Desktop Control & Window Resizing)**: Implemented `resize_window` in `AutomationService` ([`automation.py`](file:///c:/Users/ashri/JARVIS/backend/services/automation.py)) via Win32 `SetWindowPos` and registered `resize_window` tool in `ToolRegistry` for LLM function calling.
- [x] **Instant Interrupt (Barge-In)**: **Stable**. Added `cancel_playback()` method to `TTSService` for instant TTS audio cancellation.
- [x] **Exponential Backoff & Retry**: **Stable**. Implemented `exponential_backoff_retry` decorator in `backend/utils/retry.py`.
- [x] **Vision Cooldown Rate-Limiter**: **Stable**. Added 3.0-second cooldown timer to `VisionService`.
- [x] **Auto-Start on Boot**: **Stable**. Created `AutoStartService` in `backend/services/system_autostart.py` for Windows Registry (`Run`) key management.
- [x] **Clipboard Intelligence**: **Stable**. Created `ClipboardIntelligenceService` (`clipboard_intelligence.py`) for quick-action text analysis.
- [x] **Session Memory Continuity**: **Stable**. Ephemeral session summaries stored at shutdown in `data/session_memory.json` and read on startup.
- [x] **Background Monitoring & Safety**: **Stable**. Added topic monitoring to `ProactiveEngine` with content safety rules.
- [x] **Proactive 2.0 Cooldown**: **Stable**. Added 20-minute interjection cooldown (`1200s`) to `ProactiveEngine`.
- [x] **Structured Layout & Table OCR**: **Beta**. Added `extract_structured_ocr_tables` in `VisionService` using deep vision / pytesseract fallbacks (depends on pytesseract binary).
- [x] **Prash Local LLM Engine**: **Experimental**. Custom local PyTorch transformer decider (`data/prash`); functional locally, but response quality is tied to Colab fine-tuning dataset volume.
- [x] **3D Face Model Asset Integration (facecap.glb)**: **Beta**. Loaded `facecap.glb` via `GLTFLoader` with `MeshoptDecoder`. Speech amplitude visemes bound to `jawOpen` (depends on WebGL hardware acceleration).
- [x] **Fail-Closed Mobile JWT Authentication**: **Stable**. Unconditional fallback removed in `mobile_auth.py`. Returns 401 Unauthorized on invalid tokens.
- [x] **Green Hacker / Terminal Theme**: **Stable**. Applied Green Hacker Theme (`#00ff66` / `#050d08`) across CSS, Three.js shaders, and UI components.
- [x] **Resizable 70/30 Panel Splitter**: **Stable**. Implemented vertical divider bar between 3D Face Panel and Chat Panel with `localStorage` persistence.
- [x] **21 MCU Micro-Agents Framework**: **Beta**. Created `BaseMicroAgent` and `mcu_agents.py` registering all 21 MCU agents with async IPC message bus in `AgentEcosystemService`.
- [x] **Marvel Situational Personality Engine**: **Stable**. Created `PersonalityEngine` providing context-aware tone overlays (`technical`, `calm`, `serious`, `friendly`, `professional`).
- [x] **Wake Word Detection Hardware Listener**: **Beta**.
  - **Root Cause Identified**: `WakeWordService` model loading was initialized asynchronously in `main.py`, but it had **no standalone background microphone capture loop running on the Python backend**. It relied 100% on binary WebSocket audio chunks sent from the frontend client. On startup, `App.tsx` renders `FaceLockScreen` when `isLocked` is true, so `startMicCapture()` was never called on startup, leaving the backend `WakeWordService` receiving 0 bytes. Furthermore, `openwakeword` ONNX model loading takes ~29.9s cold-start on CPU during which incoming frames were dropped.
  - **Fix Implemented**: Added `start_standalone_listener()` to `WakeWordService` ([`wake_word.py`](file:///c:/Users/ashri/JARVIS/backend/services/wake_word.py)) running a dedicated `sounddevice` background microphone thread (16kHz PCM), publishing `wake_word.detected` events to `EventBus` and invoking `VoiceAgent` state transitions. Auto-started in `main.py` once model loading completes.

---

## 🟡 P4 — Real Face-Identity Security Lock Screen (**Status: Beta**)

- [x] **JARVIS Real Face-Identity Lock Screen**: **Beta**.
  - **128-d Face Biometrics**: `FaceBiometricsService.verify_face_identity(frame_bytes)` extracting 128-d feature embeddings via OpenCV SFace / feature descriptors ($\text{similarity} \ge 0.70$). Fails closed on missing/ambiguous frames.
  - **Owner Profile Enrollment**: `enroll_owner()` averaging 3 frames and hashing backup master PIN into `data/face_owner_profile.json`.
  - **Lockout & Rate-Limiting**: Enforces 3 failed attempt limit with 30-second lockout timer.
  - **Frontend Lock Screen**: `FaceLockScreen.tsx` rendering pre-mount WebRTC camera feed canvas, status HUD, Master PIN modal, and Enrollment wizard (requires physical camera for live scan).

---

## 📊 Subsystem Status Overview

| Subsystem / Layer | Operational Status | Notes & Dependencies |
| :--- | :---: | :--- |
| **P0 Core Bootstrapping** | **Stable** | FastAPI, logging, config loader, dependencies |
| **P1 Perception & Execution** | **Beta** | Win32 UIA tree capture (~15ms), WorldModel refresh (~170ms) |
| **P2 UI & Telemetry** | **Stable** | React 19 + Electron 35 shell, split panels, permission modal |
| **P3 Master Features & MCU Agents** | **Beta** | 21 Micro-Agents IPC fabric, Chat History, Personality Engine |
| **P4 Face-ID Lock Screen** | **Beta** | 128-d OpenCV face embedding, WebRTC lock screen, PIN fallback |
| **Prash Local LLM** | **Experimental** | PyTorch local transformer; quality scales with dataset size |
