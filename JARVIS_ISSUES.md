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
- [x] **HierarchicalOrchestrator Removal**: **Stable**. `backend/agents/multi_agent/orchestrator.py` completely deleted. Removed import and startup instantiation from `main.py`. Verified 0 remaining references across codebase.
- [x] **Wake Word Detection Hardware Listener**: **Beta**.
  - **Root Cause Identified**: `WakeWordService` model loading was initialized asynchronously in `main.py`, but it had **no standalone background microphone capture loop running on the Python backend**. It relied 100% on binary WebSocket audio chunks sent from the frontend client. On startup, `App.tsx` renders `FaceLockScreen` when `isLocked` is true, so `startMicCapture()` was never called on startup, leaving the backend `WakeWordService` receiving 0 bytes. Furthermore, `openwakeword` ONNX model loading takes ~29.9s cold-start on CPU during which incoming frames were dropped.
- [x] **Unauthenticated Mobile REST API Security Vulnerability Fix**: **Stable (Critical Security Fix)**.
  - **Vulnerability Identified**: All endpoints in `mobile_router.py` (~24 routes) except pairing lacked token authentication, and CORS was set to wildcard `allow_origins=["*"]`. Any host on the local network could trigger remote commands (`shutdown`, `restart`, `open_app`) without credentials. `open_app` also used `subprocess.Popen(app_name, shell=True)`, posing a shell command injection risk.
  - **Fix Implemented**: Applied router-wide `dependencies=[Depends(require_mobile_auth)]` in [`mobile_router.py`](file:///c:/Users/ashri/JARVIS/backend/api/mobile_router.py) enforcing verified JWT tokens for all endpoints except pairing (`/pair/initiate`, `/pair/confirm`, `/pair`). Fixed `open_app` by validating app names and stripping dangerous shell operators (`&`, `;`, `|`, `>`, `<`, `$`). Routed remote `shutdown`/`restart` commands through `gateway_svc.request_approval()` security gatekeeper. Tightened CORS in [`middleware.py`](file:///c:/Users/ashri/JARVIS/backend/api/middleware.py) to local loopback and private subnets (`10.x.x.x`, `172.16-31.x.x`, `192.168.x.x`). Verified with empirical 401 response logs (`scratch/test_part1_security.py` **PASSED**).
- [x] **Mobile Companion App Feature Gaps & Green Hacker Theme**: **Beta**.
  - **Theme Alignment**: Updated `ControlScreen.tsx`, `DashboardScreen.tsx`, and `ApprovalsScreen.tsx` to match Green Hacker theme (`#00ff66` accent / `#050d08` dark background).
  - **Natural Language & Voice Input**: Added prompt input field and voice command handler on `ControlScreen.tsx` routing commands to backend LLM chat / planner (`mobileClient.sendNaturalLanguageCommand`).
  - **Live Mode Surfacing**: Added Live Mode toggle switch and real-time status card on `ControlScreen.tsx` wired to `/api/v1/mobile/live_mode/toggle` and `/status`.
  - **Mobile Chat Screen**: Created `ChatScreen.tsx` allowing mobile users to view recent conversation history (`/api/v1/chat/history`) and send messages to Prash / LLM.

---

- [x] **`RequestCategory` Intent Routing & `ToolRegistry` Schema Merge**: **Stable (Architectural Fix)**.
  - **Intent Branching**: Wired `RequestCategory.LIVE_MODE_REQUEST` branching in `PlannerAgent.plan_and_execute()` ([`backend/agents/planner.py`](file:///c:/Users/ashri/JARVIS/backend/agents/planner.py#L173)), injecting live perception window context and indexed UI controls into system prompt.
  - **Tool Schema Merge**: Merged `ToolRegistry.get_tools_schema()` into `LLMService.get_tools()` ([`backend/services/llm.py`](file:///c:/Users/ashri/JARVIS/backend/services/llm.py#L965)), exposing perception-targeted tools (`click_element_by_name`, `set_control_value`, `auto_fill_form`, etc.) to LLM tool calling. Verified with empirical routing test (`scratch/test_request_category_tool_routing.py` **PASSED**).

---

## 🟢 P4 — Real Face-Identity Security Lock Screen, Liveness & Profile Persistence (**Status: Stable**)

- [x] **JARVIS Real Face-Identity Lock Screen**: **Stable**.
  - **Liveness Anti-Spoofing Verification**: Implemented frame-to-frame pixel variance and micro-movement detection in `FaceBiometricsService.verify_face_identity()` ([`backend/services/face_biometrics.py`](file:///c:/Users/ashri/JARVIS/backend/services/face_biometrics.py#L328)). Rejects 100% static photo attacks with `"Liveness check failed: Static photo or motionless frame detected"`. Verified with empirical spoofing test (`scratch/test_liveness_detection.py` **PASSED**).
  - **Durable Profile Persistence**: Enrolled face profiles (`owner_embedding`, `pin_hash`, `pin_salt`, `enrolled_at`) are saved to `data/face_owner_profile.json` on disk by `FaceBiometricsService._save_profile()` and automatically reloaded at startup via `_load_profile()`. Verified durable loading across process restarts (`scratch/test_enrollment_restart_persistence.py` **PASSED**).
  - **Service Singleton Registration**: Registered `face_biometrics_service` as a shared singleton in `ServiceManager` (`backend/main.py`), ensuring all REST endpoints (`/api/biometrics/face/status`, `/verify`, `/enroll`, `/verify_pin`) share identical in-memory lockout and profile state.
  - **128-d Face Biometrics & Primary Face Isolation**: `FaceBiometricsService.verify_face_identity(frame_bytes)` uses OpenCV Haar Cascades and feature descriptors to isolate the primary face in frame.
  - **Owner Profile Enrollment**: `enroll_owner()` averages sample frames and hashes backup master PIN into `data/face_owner_profile.json`.
  - **Lockout & Rate-Limiting**: Enforces 3 failed attempt limit with 30-second lockout timer.
  - **Frontend Lock Screen**: `FaceLockScreen.tsx` rendering pre-mount WebRTC camera feed canvas, status HUD, Master PIN modal, and Enrollment wizard.

---

## 🟢 P5 — Data Hygiene, Configurable Offline Mode & Multi-Step Pipeline Planning (**Status: Stable**)

- [x] **Data Hygiene & Zero Personal Runtime Data in Repository**: **Stable (Privacy Fix)**.
  - **Audit & Cleanup**: Cleared all personal conversation histories, device pairings, facial embeddings, user habits, and search data from `backend/data/trusted_devices.json`, `data/trusted_devices.json`, `backend/data/memory/episodic_memory.json`, `data/face_owner_profile.json`, `data/monitored_topics.json`, and `data/prash/agent_memory.json`. Replaced with empty template schemas (`{}` or `[]`).
  - **Git Exclusion**: Updated `.gitignore` to explicitly cover `data/`, `backend/data/`, `*.db`, `*.sqlite`, `*.bin`, `*.key`, `trusted_devices.json`, `episodic_memory.json`, `face_owner_profile.json`, `user_habits.json`, and `vault.key`. Fresh checkouts start completely clean, auto-creating state files on first run.
- [x] **Configurable Offline Mode**: **Stable**.
  - **Settings Integration**: Added `FORCE_OFFLINE_MODE: bool = Field(default=True)` to `Settings` in `backend/config.py`.
  - **Dynamic Environment Configuration**: Updated `backend/main.py` to read `FORCE_OFFLINE_MODE` from `get_settings()`, dynamically setting or unsetting `HF_HUB_OFFLINE` and `TRANSFORMERS_OFFLINE`.
- [x] **UnifiedPipeline Real Multi-Step Planning**: **Stable**.
  - **LLM Task Decomposition**: Replaced one-line placeholder string in `UnifiedPipeline` ([`backend/agents/unified_pipeline.py`](file:///c:/Users/ashri/JARVIS/backend/agents/unified_pipeline.py#L76)) with `_generate_plan_steps(user_request)`, prompting LLM service for 2-5 ordered subtasks.
  - **Multi-Part Conjunction Fallback**: Added rule-based fallback splitting multi-part conjunctions ("and then", "then", "&", "and") into distinct sub-steps.
  - **Verification**: Tested with multi-part prompt `"check the weather and then tell me a joke"`, generating: `Step 1: Check the weather`, `Step 2: Tell me a joke` (`scratch/test_unified_pipeline_multistep.py` **PASSED**).

## 🟢 P6 — Leftover 3D Model Asset Cleanup & Live Mode Hand-Gesture Cursor Control (**Status: Stable**)

- [x] **Leftover 3D Face Asset Cleanup**: **Stable**.
  - **Audit**: Verified zero code files across `frontend/src` or `backend` referenced `facecap.glb` or `head.glb`.
  - **Removal**: Deleted leftover 332KB GLB model files from `frontend/src/renderer/src/assets/models/` and `frontend/src/renderer/public/models/`. `FaceLockScreen.tsx` and backend biometrics services were kept completely intact.
- [x] **Live Mode Scoped Hand-Gesture Cursor Control**: **Stable**.
  - **Audit Report**: `handTracker.ts` was instantiated inside `LiveModeCard.tsx` when `handControlEnabled` was true, but was not gated to Live Mode being active.
  - **Live Mode Gating**: Updated `LiveModeCard.tsx` to gate `HandTracker` activation strictly to `isEnabled && handControlEnabled`. Turning Live Mode OFF (`isEnabled = false`) immediately stops `HandTracker`, releasing camera & MediaPipe loops.
  - **Real Gesture Mapping & Throttling**:
    - **Move**: Index tip position mapped to screen coordinates with Holt's linear trend smoothing filter and 15ms / 2px movement throttling.
    - **Click & Drag**: Single left pinch release (<450ms) -> click; double pinch release -> double_click; held left pinch + drag (>25px) -> `press` (mouse down) and `release` (mouse up).
    - **Right Click**: Thumb + Middle tip pinch -> right click.
    - **Scroll**: Two fingers raised (Index & Middle raised, Ring & Pinky folded) + vertical movement -> `scroll(direction, amount)`.
    - **Escape & Volume**: Escape (Thumb+Pinky) and Volume (Thumb+Ring) retained and fully operational.
  - **Verification**: Tested backend `HandControlService` native win32 cursor simulation (`scratch/test_hand_control_service.py` **PASSED**) and clean production build (`npm run build` **PASSED in 33.66s**).

---

## 📊 Subsystem Status Overview

| Subsystem / Layer | Operational Status | Notes & Dependencies |
| :--- | :---: | :--- |
| **P0 Core Bootstrapping** | **Stable** | FastAPI, logging, config loader, dependencies |
| **P1 Perception & Execution** | **Beta** | Win32 UIA tree capture (~15ms), WorldModel refresh (~170ms) |
| **P2 UI & Telemetry** | **Stable** | React 19 + Electron 35 shell, split panels, permission modal |
| **P3 Master Features & MCU Agents** | **Beta** | 21 Micro-Agents IPC fabric, Chat History, Personality Engine |
| **P4 Face-ID Lock Screen** | **Stable** | 128-d OpenCV face embedding, WebRTC lock screen, PIN fallback |
| **P5 Privacy, Offline & Pipeline** | **Stable** | Clean template repos, configurable offline mode, multi-step planning |
| **P6 Hand-Gesture Control & Asset Cleanup** | **Stable** | Live Mode scoped MediaPipe gesture tracker, win32 cursor control |
| **P7 WebSocket & Queue Infrastructure** | **Stable** | Cold-start health polling, net.Socket upgrade fix, outbound queueing |
| **Prash Local LLM** | **Experimental** | PyTorch local transformer; quality scales with dataset size |

---

## 🟢 P7 — Robust WebSocket Infrastructure, Cold-Start Health Polling & Zero-Loss Outbound Message Queueing (**Status: Stable**)

- [x] **Vite Proxy Upgrade Error Handling (1006 Root Cause Resolution)**: **Stable**.
  - **Empirical Evidence & Root Cause**: During cold start, Vite proxy (`electron.vite.config.ts`) received WebSocket upgrade requests (`/ws`) before FastAPI opened port 8000. The proxy `error` handler attempted to call `res.writeHead(503)` on the socket. For WebSocket upgrade requests, `res` is an instance of a TCP `net.Socket` (not `http.ServerResponse`), causing an unhandled socket error that destroyed the stream instantly and triggered browser `WebSocket connection failed: Code 1006` errors.
  - **Fix Implemented**: Updated `electron.vite.config.ts` proxy error callback to inspect `req.headers.upgrade === 'websocket'` and call `req.socket.destroy()` cleanly without throwing unhandled exceptions.
- [x] **Backend Health Check Readiness Polling**: **Stable**.
  - **FastAPI Readiness Gate**: Updated `useWebSocket.ts` to poll `http://127.0.0.1:8000/health` up to 12 times (400ms interval) before instantiating `new WebSocket()`. Ensures the backend port is bound and active, eliminating startup connection race conditions.
- [x] **Zero-Loss Outbound Message Queueing & Re-sending**: **Stable**.
  - **Outbound Queue**: Added `outgoingQueue` to `useWebSocket.ts`. Any text or command message sent while `globalWs.readyState !== WebSocket.OPEN` is safely enqueued.
  - **Automatic Flush**: Upon WebSocket `onopen`, all queued outbound messages are automatically flushed to the backend in order.
  - **UI Notification**: Added `[WS Queue]` notice in chat when messages are queued during reconnect windows.
- [x] **Real-Time Visible Connection Status Pill**: **Stable**.
  - Added live status indicator pill in `ChatPanel.tsx` header bar rendering real-time states: `🟢 CONNECTED`, `🟡 RECONNECTING (N QUEUED)`, `🔵 CONNECTING...`, and `🔴 OFFLINE`.


