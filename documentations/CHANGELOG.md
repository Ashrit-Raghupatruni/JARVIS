# 📝 CHANGELOG — JARVIS Personal AI Operating System

All notable changes and architectural upgrades to JARVIS are documented in this file.

## [1.6.0-master-reliability-and-durability-fix] - 2026-09-28

### 🏎️ Parallel Racing LLM Provider Selection (Top-3 Circuit)
- **Zero-Stall Provider Racing**: Implemented `LLMRacingCircuit` (`backend/services/llm/racing.py`) that fires prompts concurrently across the top 3 ranked providers using `asyncio.wait(return_when=FIRST_COMPLETED)`.
- **Response Validation Criteria**: Implemented strict response validation requiring non-null output, $>10$ characters, zero error patterns (`timeout`, `quota exceeded`, `connection refused`), and Shannon entropy $<6.0$ to discard gibberish.
- **Immediate Task Abort & Cancellation**: Immediately aborts losing tasks (`task.cancel()`) and closes active streams (`aclose()`) to conserve user quota and tokens.
- **50ms Simultaneous Tie-Breaking**: Applies historical ranking priority when providers complete within 50ms of each other.
- **Fail-Safe Sequential Fallback**: Automatically invokes a sequential 4th retry if all top-3 providers fail before falling back to local Prash engine.
- **Router Scoring Integration**: Added dynamic `speed_score_bonus` (+20 for winner, +5 for slower valid responses, -10 for failure) and `GET /router/racing` observability metrics.

### 💾 Persistent SQLite WAL Task Queue & Zero-Wipeout Navigation
- **Durable Task Model**: Replaced volatile in-memory dictionary in `TaskQueueManager` (`backend/services/task_queue.py`) with SQLite WAL-backed table `persistent_tasks` (`id`, `title`, `command`, `priority`, `status`, `progress`, `logs_json`, `result`, `error`, `created_at`, `updated_at`).
- **Full REST API Suite**: Added authoritative endpoints in `backend/api/routes.py`:
  - `GET /api/v1/tasks`: Lists all persisted tasks ordered by priority and recency.
  - `POST /api/v1/tasks`: Enqueues and persists new user or autonomous tasks.
  - `POST /api/v1/tasks/{id}/pause`: Pauses execution and updates SQLite state.
  - `POST /api/v1/tasks/{id}/resume`: Resumes execution and updates SQLite state.
  - `DELETE /api/v1/tasks/{id}`: Cancels execution and persists status.
  - `POST /api/v1/tasks/reorder`: Updates user-defined execution priorities.
- **Frontend Navigation Durability**: Upgraded `frontend/src/renderer/src/components/TaskQueueManager.tsx` to fetch authoritative tasks on mount and listen to WebSocket `task_update` events. Tasks now permanently survive tab switches, page reloads, and application reboots.

### 🛡️ Long-Horizon Goal Continuity & Self-Recovery Engine
- **Singleton Management**: Exported global singleton `long_horizon_manager = LongHorizonCheckpointService()` in `backend/services/long_horizon_checkpoint.py`.
- **Automated Reboot Recovery**: Upgraded `recover_interrupted_goals()` and `POST /api/v1/developer/recover_interrupted_goals` to scan for dangling `running` goals on boot, save state checkpoints, transition to `paused_for_resume`, and resume seamlessly without losing progress.

### 🎙️ Voice Pipeline Hardening & STT Sentence Preservation
- **Stutter Truncation Bug Resolved**: Repaired `clean_whisper_hallucinations` in `backend/services/voice/stt_manager.py`. It now collapses repeated token loops (e.g. `"How many How many How many"`) while preserving the entire substantive user query (`"How many finger does humans have?"`).
- **Transcript Validation Gate**: Added `is_valid_transcript()` rejecting single-character transcripts (`"I"`), punctuation-only inputs, and filler noise (`"uh"`, `"watching"`, `"[music]"`) before triggering the planner.
- **Prash Timeout Protection**: Wrapped Prash neural inference in `planner.py` with a 2.5s fail-safe timeout to prevent hanging on high-entropy queries.

### 🔌 ChromaDB PostHog Isolation & Windows Socket Resilience
- **PostHog Telemetry Monkeypatch**: Patched `chromadb.telemetry.product.posthog.Posthog.capture` and `_direct_capture` to no-ops in `bootstrap.py` and `manager.py`, eliminating `TypeError: capture() takes 1 positional argument but 3 were given` caused by PostHog 7.15+ library updates.
- **Windows Socket Resilience**: Added unhandled `OSError` (`WinError 64` / `10053`) protection in `websocket.py` and `mobile_ws.py` to gracefully disconnect dropped sessions without crashing the host process.
- **Fuzzy Phonetic App Resolution**: Enhanced `_resolve_app_path` in `desktop_executor.py` with phonetic mapping tables and `difflib` matching ("nor not bad" -> notepad).

### 🧪 Comprehensive Verification Suite (100% Pass Rate)
- Added `test_racing_circuit.py` (12 tests), `test_canonical_contracts_and_bypasses.py` (6 tests), and `test_reliability_audit.py` (7 tests).
- All 45 focused reliability audit tests and all 340 master backend test suite tests pass at 100%.
- Frontend Vite build compiles cleanly with zero errors in 2.62s.

---

## [1.5.0-secure-telegram-bot-integration] - 2026-09-27

### 🤖 Secure Telegram Bot Remote Control & Notification Gateway
- **Zero-Duplicate Assistant Architecture**: Incoming Telegram text and commands route directly into the existing JARVIS core execution pipeline (`FastIntentRouter`, `PlannerAgent`, `ToolRegistry`, `SafetyGatekeeper`, `ActionExecutionVerifier`, `WorldModel`, and `MemoryService`) with interactions tagged as `source="telegram"`.
- **Strict Authentication & Security Gate**: Constant-time verification on authorized user ID (`TELEGRAM_CHAT_ID`). Rejects all unknown or unauthorized senders fail-closed with immediate security audit alerts.
- **Fail-Closed Companion Pairing Mode**: If `TELEGRAM_CHAT_ID` is unassigned, bot enters Pairing Mode, generates a 6-digit numeric pairing PIN on the desktop HUD, and safely pairs the user via `/pair <PIN>`, persisting the chat ID to `.env`.
- **Remote Capabilities Supported**:
  - `/status`, `/telemetry`: Hardware metrics (CPU, RAM, Disk), active LLM provider, and system state.
  - `/tasks`, `/progress`: Live inspection of `AsyncTaskQueue` items and step-by-step progress tracking.
  - `/lock`: Instant Windows workstation lock via `rundll32.exe user32.dll,LockWorkStation`.
  - `/screenshot`: Live desktop capture delivered directly as an uncompressed Telegram photo.
  - `/cancel`: Immediate cancellation of running background tasks and VoiceManager speech interrupt.
  - `/app <name>`: Whitelisted desktop application launching with strict shell injection defense.
  - **Natural Language Interaction**: Full conversational reasoning, web search, memory lookup, and multi-step tool execution.
- **1-Click Inline Approval System**: Interactive cards sent with `[✅ Approve Action]` and `[❌ Deny Action]` inline keyboard buttons. Tapping instantly unblocks or denies pending `MobileGatewayService` and `MobileBridgeService` execution promises.
- **Notification Debounce & Flood Defense**: Built-in 2.0s rate-limiting buffer and 10-second duplicate message suppression to protect against Telegram API rate limits.
- **Desktop UI Integration (`TelegramIntegrationCard.tsx`)**: Embedded inside the Settings `Integrations` tab with live connection status, bot identity (`@playingwdbot_bot`), masked chat ID, pairing PIN generator, and test notification triggers.
- **Automated Verification Suite (`test_telegram_remote_service.py`)**: 17 runtime security and integration tests passing at 100%.

---

## [1.4.0-client-independent-core-and-mobile-modernization] - 2026-09-27

### 🌐 Client-Independent JARVIS Core Architecture & Unified Endpoints
- **Unified Core Endpoints**: Standardized root and versioned REST endpoints across `GET /health`, `GET /status`, `GET /system/status`, `GET /device/info`, `POST /device/pair`, `GET /history`, `POST /command`, `POST /settings`, and `WS /ws`.
- **Authoritative Runtime Diagnostics Model**: Introduced `RuntimeDiagnosticsModel` / `RuntimeDiagnostics` schema in `backend/models/schemas.py`. Dynamically resolves the actual active LLM provider (`active_provider`) and active model (`active_model`) from `llm_service.get_runtime_info()`, accurately reporting Ollama, Gemini, Groq, OpenRouter, or OpenAI without exposing credentials or API keys.
- **Fail-Closed Companion Pairing**: Integrated `POST /device/pair` supporting 6-digit numeric PIN, Ed25519 QR payload verification (`jarvis_pair://`), and cryptographic JWT issuance with fail-closed security.
- **LAN Device Discovery**: `GET /device/info` dynamically gathers host information, platform identifiers, and local network LAN IPv4 addresses for seamless zero-configuration discovery.

### ⚡ Version 1 WebSocket Protocol & Request Correlation
- **Versioned Protocol Envelope**: Enforced strict `version: "1"` envelope on `WSMessage` with `request_id`, `session_id`, `msg_id`, `type`, `timestamp`, and strongly typed `data`.
- **Request-to-Response Correlation**: Propagated client `request_id` through the decoupled background execution worker in `backend/api/websocket.py` to all downstream acknowledgments, task progress milestones (`agent_progress`), and assistant responses.
- **Strict TypeScript Protocol Definitions**: Created `frontend/src/renderer/src/types/protocol.ts` and `mobile_app/src/types/protocol.ts` with discriminated unions for all server and client messages without a single `any` type.

### 📱 Robust Connection Manager & Mobile Services
- **Autonomous Lifecycle & Reconnect**: Implemented `RobustConnectionManager` in `mobile_app/src/services/connectionManager.ts` featuring exponential backoff with random jitter (1s to 30s), active heartbeat keep-alive with ping/pong timeout detection, foreground/background lifecycle awareness, and an observable state machine (`connecting`, `connected`, `reconnecting`, `offline`, `error`).
- **Correlated Command Promises**: Added `sendCommandCorrelated(text, conversationId)` returning typed response promises correlated via `request_id`.

### 🎨 Mobile-First UI Modernization & Unified Design System
- **Phone-Native Information Architecture**: Rebuilt mobile navigation into 5 core bottom-dock tabs: `Home`, `Chat`, `Voice`, `Apps`, and `More`.
- **Futuristic Minimalist Dark Aesthetic**: Standardized on `#02040a` deep void background with glowing cyan and indigo accents across mobile and desktop.
- **Mobile Component Suite**: Built `JarvisMobileCoreOrb` (multi-state animated SVG orb with IDLE, LISTENING, PROCESSING, EXECUTING, SPEAKING, ERROR, OFFLINE), `HeaderGreeting`, `QuickPromptPills`, `QuickActionsBentoGrid`, `CommandInputPill`, and `FloatingBottomDock`.
- **Desktop Sub-Page Harmonization**: Unified all 9 desktop sub-pages (`Home`, `Chat`, `Voice`, `Tasks`, `PC Control`, `Files`, `Automation`, `System`, `Settings`) with consistent glassmorphism, floating HUD, and responsive layouts.

### 🧪 Automated Testing & Verification
- **Full Backend Pytest Suite**: **298/298 passed** (100% pass rate in 116.16s) across all 31 test files.
- **Frontend TypeScript Gate**: **0 errors** (`npx tsc --noEmit` in `frontend/`).
- **Mobile TypeScript Gate**: **0 errors** (`npx tsc --noEmit` in `mobile_app/`).

---

## [1.3.0-live-mode-failover-and-hermes-integration] - 2026-09-26

### 🔄 Live Mode Failover Architecture & Agent Supervisor
- **Single-Agent Control Lock (`_control_lock`)**: Implemented `LiveModeFailoverSupervisor` in `backend/services/live_mode/failover_controller.py` with strict `asyncio.Lock()` mutual exclusion ensuring JARVIS Desktop Agent and Hermes Desktop Agent never issue simultaneous mouse or keyboard inputs.
- **Explicit Authority Lifecycle**: Introduced strict state machine transitions (`PRIMARY_ACTIVE` ➔ `FAILOVER_PENDING` ➔ `HERMES_ACTIVE` ➔ `RECOVERY` ➔ `COMPLETED` / `FAILED` / `CANCELLED`).
- **Dynamic Step Tracking**: Per-step execution tracking (`PENDING`, `RUNNING`, `SUCCESS`, `FAILED`, `TIMEOUT`, `BLOCKED`).
- **Seamless Failure Point Resume**: Primary failure compiles handoff payload (`completed_steps`, `failed_step`, `error_reason`, screen context) and transfers control to Hermes to finish remaining steps without repeating completed ones.
- **Emergency Stop / Take Control**: Real-time interrupt and control lock revocation.
- **Live Mode Failover HUD (`LiveModeFailoverHUD.tsx`)**: Real-time Electron HUD component displaying active agent badges, failover alerts, and manual takeover button.

### 🌉 12-Pillar Hermes Bridge Service & Dual Agents
- **Hermes Bridge Service (`backend/services/hermes_bridge.py`)**: 12-pillar bridge covering tool execution, agent orchestration, command routing, computer control bridge, task automation, background workers, context sync, local dev, extensibility, error boundary, permission boundaries, and WebSocket progress streaming.
- **Hermes Desktop Agent (`backend/agents/desktop_agent.py`)**: Dedicated Windows 11 desktop executor with `AttachThreadInput` foregrounding, clipboard typing (`Ctrl+V`), and coordinate clicks.
- **Hermes General Agent (`backend/agents/hermes_agent.py`)**: Multi-step LLM function calling agent operating over all 69 JARVIS system tools.
- **Hermes Orchestrator (`backend/agents/hermes_orchestrator.py`)**: Task routing and multi-agent coordination.
- **Hermes CLI Secrets Sync**: Automatically synchronized `.env` API keys to `C:\Users\ashri\AppData\Local\hermes\.env` and `~/.hermes\.env`. Verified with `hermes doctor` and `hermes setup`.

### 🎨 In-Chat Image Generation Engine & Lightbox Studio
- **Dual-Engine Image Generator (`ImageGeneratorService` in `backend/services/image_generator.py`)**: Google Imagen 3 with automatic fallback to Pollinations AI and local disk caching under `data/generated_images/`.
- **Frontend Lightbox (`ChatPanel.tsx`)**: Glassmorphism image preview cards in chat with full-screen Lightbox zoom, panning, clipboard copy, and download actions.
- **Truthful Tool Registry**: Registered `generate_image`, `live_mode_execute_task`, `live_mode_emergency_stop`, `hermes_bridge_task`, `hermes_async_task`, `hermes_agent_task`, `hermes_orchestrator_task`, and `desktop_agent_task` (Total tool count: **69 executable tools**).

### 🧪 Automated Testing & Verification
- **Test Suite**: Verified all 12 failover, dual Hermes, and image generator tests. Full test suite execution: **298 passed in 216.80s** with zero regressions across 30 test files.
- **Frontend TypeScript Build**: Clean compilation `npx tsc --noEmit` (0 errors).

---

## [1.2.0-production-upgrade] - 2026-08-20

### 🛡️ Fail-Closed Security Bridge & Gatekeeper Hardening
- **Strict Fail-Closed Policy**: Completely overhauled `MobileBridgeService` (`backend/services/mobile_bridge.py`). Replaced all fail-open fallback returns with strict `return False` on missing bot config, API transport failures, timeouts, and unknown states.
- **Explicit Approval Lifecycle**: Introduced `ApprovalState` enum (`PENDING`, `APPROVED`, `DENIED`, `TIMEOUT`, `ERROR`) with structured security audit logging (`[SECURITY] Action: <id> | State: <state> | Target: <target>`).
- **Empirical Verification**: Verified via `scratch/test_fail_closed.py` and `scratch/test_outcome_based_verification.py` (Unconfigured bot denied, timeout denied, explicit approval authorized).

### 🎙️ Offline-Independent Dual-Provider TTS Engine
- **Provider-Based Architecture**: Abstracted `TTSService` (`backend/services/tts.py`) into `EdgeTTSProvider` (online Microsoft streaming neural audio) and `LocalTTSProvider` (Windows Native SAPI `SpVoice` / `SpFileStream`).
- **Zero-Exception Offline Failover**: Added seamless automatic fallback to local SAPI when internet connectivity is unavailable or when Edge-TTS raises connection errors.
- **Barge-In Preservation**: Preserved thread-safe cancellation and instant interruption stopping (`cancel()`, `cancel_playback()`).
- **Empirical Verification**: Verified offline WAV audio synthesis (159,640 bytes generated locally via SAPI).

### 📱 Real Mobile Voice Input & Real-Time Approvals
- **Voice Simulation Eradication**: Removed `simulateVoiceInput()` and hardcoded text injections in `mobile_app/src/screens/ControlScreen.tsx`.
- **Microphone Capture & WebSocket STT**: Added recording state machine (`handleVoiceButtonPress`, `Idle` -> `Listening...` -> `Processing...` -> `Response`) and base64 audio streaming to backend `faster-whisper` STT via `mobile_ws.py`.
- **Dynamic Mobile Approvals**: Removed hardcoded mock approval item (`appr_101`) in `mobile_app/src/screens/ApprovalsScreen.tsx`. Wired dynamic WebSocket `approval_request` events and REST fetch (`fetchPendingApprovals`) with interactive 1-click Approve/Deny.

### 👁️ Standalone Backend Hand Gesture Tracking Worker
- **Decoupled OpenCV Worker**: Built `CameraWorker` background thread in `HandControlService` (`backend/services/hand_control_service.py`) for direct webcam frame capture (`cv2.VideoCapture`).
- **Gesture Classification & Debouncing**: Integrated `GestureEngine` for landmark classification (`PINCH`, `OPEN_PALM`, `FIST`, `SWIPE`) with confidence filtering (`0.7`) and temporal debouncing (`150ms`) to eliminate click jitter. Works even when the Electron window is minimized.

### 🤖 Real MCU Micro-Agent Domain Handlers
- **Domain Operation Integrations**: Upgraded `backend/agents/micro_agents/mcu_agents.py` from default echo handlers to real domain operations:
  - `CalendarAgent`: Formats daily agenda and forecast timelines.
  - `ReminderAgent`: Queues time-based reminders in task queue.
  - `AutomationAgent`: Binds to `AutomationService` and `N8nIntegrationService`.
  - `DeviceAgent`: Gathers live CPU/RAM/Disk metrics via `psutil`.
  - `SecurityAgent`: Evaluates action risk via `SafetyService`.
  - `SelfDiagnosticAgent`: Sweeps system diagnostic metrics.
- **Empirical Verification**: Passed `scratch/run_ecosystem_tests.py` and `scratch/test_outcome_based_verification.py`.

### ⚡ n8n Fast Pre-Flight Probing (<250ms)
- **Non-Blocking Socket Probe**: Implemented `_is_reachable()` TCP socket check in `N8nIntegrationService` (`backend/services/n8n_service.py`).
- **Latency Optimization**: Reduced offline failure detection latency from 4.12s to ~250ms.
- **Tool Suite Alignment**: Added `trigger_workflow` alias, `get_execution_status`, and `handle_incoming_webhook` matching all 6 ToolRegistry tools.

### 🧹 Codebase Hygiene & Mock Eradication
- **Syntax & Runtime Fixes**:
  - Replaced `os.time()` with `time.time()` in `SelfDevelopmentService` (`backend/services/self_development_service.py`).
  - Removed duplicate `class VoiceAgent:` header on line 117 in `backend/agents/voice.py`.
  - Added missing typing imports (`Dict, Any, List, Optional`) in `backend/main.py`.
  - Updated `scratch/test_n8n_integration.py` to test all 6 registered n8n tools.

---

### 🌟 LATEST IMPLEMENTATION UPDATE (2026-08-20)
- **Fail-Closed Security**: 100% fail-closed Telegram bridge and permission gates.
- **Offline TTS**: Local SAPI dual-provider voice synthesizer operational.
- **Real Mobile Companion**: Microphone streaming and dynamic gatekeeper approvals wired.
- **Backend CV Worker**: MediaPipe / OpenCV background hand tracker with debouncing.
- **MCU Domain Agents**: Real domain processing across Calendar, Reminder, Automation, Device, Security.
- **Fast n8n Probe**: Sub-250ms offline failure detection.
- **Outcome-Based E2E Verification**: 6/6 checks passed (100% success).

---

### 🏁 CURRENT SYSTEM STATUS
- **Core AI & Request Router**: ✅ WORKING / VERIFIED
- **Unified Tool Registry (18 Tools)**: ✅ WORKING / VERIFIED
- **Modular Skills Registry (20 Skills / 106 Tools)**: ✅ WORKING / VERIFIED
- **Prash PyTorch AI Engine (0.7M & 397M configs)**: ✅ WORKING / VERIFIED
- **Voice STT (faster-whisper) & Wake Word (openwakeword)**: ✅ WORKING / VERIFIED
- **Voice TTS (Edge-TTS + Local SAPI Fallback)**: ✅ WORKING / VERIFIED
- **Computer Vision & Win32 UI Automation**: ✅ WORKING / VERIFIED
- **Backend Hand Tracking CV Worker**: ✅ WORKING / VERIFIED
- **n8n Workflow Automation & Canvas Sync**: ✅ WORKING / VERIFIED
- **Memory (ChromaDB RAG + SQLite WAL)**: ✅ WORKING / VERIFIED
- **Mobile Companion App (HUD, Control, Pairing, Gatekeeper)**: ✅ WORKING / VERIFIED
- **Mobile Companion Voice Streaming**: ✅ WORKING / VERIFIED
- **Desktop Electron Dashboard & 3D WebGL Orb**: ✅ WORKING / VERIFIED
- **Autonomous MCU Micro-Agents Ecosystem (21 Agents)**: ✅ WORKING / VERIFIED
- **Prash 397M Full 50-Epoch Colab GPU Training**: 🔵 PLANNED / PENDING GPU RUN

---

## [1.1.0-master-upgrade] - 2026-07-29

### 💬 Persistent Chat History (Claude/GPT-Style)
- **Database & CRUD Methods**: Implemented `get_conversation`, `rename_conversation`, `delete_conversation`, and `auto_generate_title` in `MemoryService` (`backend/services/memory.py`).
- **REST API Endpoints**: Exposed `/api/conversations` (GET, GET by ID, PUT rename, DELETE) in `backend/api/routes.py`.
- **React Sidebar UI**: Created `ConversationSidebar.tsx` rendering persistent session lists with inline title editing, deletion, and transcript restoration into `ChatPanel.tsx`.

### 🌐 Live Mode Browser Automation Engine
- **Perceive-Decide-Act-Observe Loop**: Built `run_browser_agent` and `perceive_page_state` in `BrowserService` (`backend/services/browser.py`) leveraging Playwright cleanly without external package dependencies.
- **Tool Registry Integration**: Registered `browser_agent_task` tool in `ToolRegistry` for natural language multi-step web navigation.

### ⚡ Proactive Desktop Intelligence Suite
- **Instant Interrupt (Barge-In)**: Added `cancel_playback()` method to `TTSService` (`backend/services/tts.py`) for immediate audio stream cancellation on user speech.
- **Exponential Backoff & Retry**: Implemented `exponential_backoff_retry` decorator in `backend/utils/retry.py` for cloud LLM and web search retries.
- **Vision Cooldown Rate-Limiter**: Added 3.0-second rate-limiting timer to `VisionService`.
- **Auto-Start on Boot**: Created `AutoStartService` (`backend/services/system_autostart.py`) managing Windows Registry (`Run`) startup keys.
- **Clipboard Intelligence**: Built `ClipboardIntelligenceService` (`backend/services/clipboard_intelligence.py`) for quick-action text processing (Translate, Summarize, Explain, Fix).
- **Assistant & User Customization**: Added dynamic runtime name customization (`update_custom_names`) to `ConfigurationManager` (`backend/services/config_manager.py`).
- **Session Memory Ephemeral Continuity**: Implemented 1-2 sentence session summaries stored in `data/session_memory.json` on shutdown, mentioned once on boot and reset.
- **Background Topic Monitoring**: Integrated topic watcher in `ProactiveEngine` with hardcoded safety guardrails blocking crypto/trading spam.
- **Proactive 2.0 Cooldown**: Enforced a 20-minute interjection cooldown timer (`1200s`) in `ProactiveEngine`.

### 👁️ High-Precision Structured OCR Fallback
- **Structured Table & Bounding Box Extraction**: Added `extract_structured_ocr_tables` in `VisionService` supporting PP-StructureV3 deep vision, pytesseract, and PIL grid fallback for bounding box extraction.

---

## [1.0.0-upgrade] - 2026-07-26

### 🧠 Local AI Orchestration & Prash Engine
- **Prash Local AI Engine Primary Handoff**: Wired `PrashEngine` (`backend/services/prash/engine.py`) as the primary local reasoning engine. Token entropy evaluation determines local execution vs. explicit logged cloud fallback.
- **Identical Tool Schema Injection**: Standardized tool schemas, conversation history, and real-time World Model context injected into both Prash local engine and cloud LLM fallback cascades.
- **Evaluation Loop & Quality Diagnostic**: Established prompt evaluation suite (`scratch/test_trained_prash.py`) verifying local response quality across casual conversation, tool routing, and context continuity.

### 🖥️ Desktop Perception, Self-Healing & Automation
- **Win32 UIA Scene Graph Parser (`UIASceneGraph`)**: Sub-30ms capture of native Windows control trees, interactive buttons, form textboxes, and active window PID.
- **Interactive Python Script Launcher**: Updated `AutomationService.open_application` to launch `.py` scripts in dedicated interactive command prompts (`start cmd /k python ...`), preventing execution timeouts on interactive scripts.
- **Self-Healing Recovery Interlock (`SelfHealingEngine`)**: Fixed dictionary key mismatch (`"recovered"` vs `"success"`), restoring automatic fault diagnosis and execution path recovery.
- **Workspace Intelligence (`WorkspaceIntelligenceService`)**: Dynamic tracking of active project context, operational goals, session workflows (`coding`, `research`, `study`), 20-action ring buffer, and habit prediction matrices stored in `data/user_habits.json`.
- **Proactive Repetitive Action Advisory**: Updated `ProactiveEngine` to monitor action history and offer macro skill automation when manual desktop sequences repeat.

### 🛡️ Security, Safety & Mobile Companion
- **Electron Exit Interlock Fix**: Imported Electron `net` module in `frontend/src/main/index.ts` enabling desktop exit gatekeeper approval requests over local HTTP.
- **Interactive Safety Permission Modal (`SafetyPermissionModal.tsx`)**: Desktop UI modal rendering `permission_request` WebSocket events with interactive Approve/Deny buttons.
- **Mobile Mission Control**: Paired 8-tab Android companion app with remote command execution, desktop shutdown gatekeeper interlocks, and real-time telemetry HUD streaming.

### 🎨 Visual HUD & Debug Inspector
- **"What JARVIS is Seeing" Visualizer (`LivePerceptionVisualizer.tsx`)**: Embedded live scene graph and Workspace Intelligence card rendering active project, workflow classification, and habit predictions.
- **Debug Inspector Tool Registry Self-Test Fix**: Added `@property def tools(self)` to `ToolRegistry`, achieving 100% self-test pass rate across all 6 core subsystems.
- **Engine Source Badges**: Displayed `⚡ Prash Local` badges on chat bubbles in `ChatPanel.tsx`.

---

## 📑 Verification Status
- **Backend Build & Route Verification**: PASSED 100% (6/6 Subsystems).
- **Frontend Production Build**: `npm run build` PASSED (`out/renderer/assets/index-B2LXqI54.js`).
