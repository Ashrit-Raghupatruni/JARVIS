# 📝 CHANGELOG — JARVIS Personal AI Operating System

All notable changes and architectural upgrades to JARVIS are documented in this file.

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
