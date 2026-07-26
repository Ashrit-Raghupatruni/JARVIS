# 📝 CHANGELOG — JARVIS Personal AI Operating System

All notable changes and architectural upgrades to JARVIS are documented in this file.

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
