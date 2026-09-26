# 📐 Technical Specification (TechSpec)

This document provides the high-level technical specifications, stack requirements, component boundaries, and performance benchmarks for JARVIS. **Last Updated:** September 26, 2026

---

## 1. Technology Stack Specification

| Layer | Technologies & Frameworks |
|---|---|
| **Frontend Framework** | React 19, TypeScript 5, Vite, Electron 30, TailwindCSS, Lucide Icons |
| **3D Render Engine** | Three.js (r164), WebGL 2, `GLTFLoader`, `MeshoptDecoder`, Custom PBR Shaders |
| **3D Asset** | `facecap.glb` (332.8 KB, Three.js dev examples) with ARKit morph targets |
| **Backend Core** | Python 3.11, FastAPI, Uvicorn, Asyncio Event Loop, Loguru |
| **Database** | SQLite3 with WAL (Write-Ahead Logging) and FTS5 Full-Text Search |
| **Failover Supervisor** | `LiveModeFailoverSupervisor` with single-agent `asyncio.Lock()` mutual exclusion |
| **Hermes Execution Layer**| 12-Pillar `HermesBridgeService`, `HermesDesktopAgent`, `HermesGeneralAgent`, `HermesOrchestrator` |
| **Image Generation** | `ImageGeneratorService` (Google Imagen 3 + Pollinations AI fallback) |
| **Agent Ecosystem** | `AgentEcosystemService`, `SubAgentInstance`, `LongHorizonCheckpointService`, `KVCachePruner` |
| **Security & Auth** | PyJWT (`HS256`), `SafetyGatekeeper` AST & Policy Engine, Ed25519 Mobile Cryptographic Interlock |

---

## 2. Component Boundaries & API Interconnects

```
 ┌────────────────────────────────────────────────────────────────────────┐
 │                      React / Electron Renderer                         │
 │  - Hero Visualizer (IdleHUD.tsx / TalkingFace3D.tsx)                   │
 │  - Live Mode Failover HUD (LiveModeFailoverHUD.tsx)                    │
 │  - AI Chat & Image Lightbox Studio (ChatPanel.tsx)                     │
 │  - AutonomousAgentStudio.tsx (Sub-agents, IPC logs, Goals, Pruner)     │
 └───────────────────────────────────┬────────────────────────────────────┘
                                     │ WebSocket / REST API
 ┌───────────────────────────────────▼────────────────────────────────────┐
 │                          FastAPI Backend Core                          │
 │  - ServiceManager Container & Lazy Bootstrap                           │
 │  - LiveModeFailoverSupervisor (JARVIS Primary ➔ Hermes Fallback)       │
 │  - HermesBridgeService (12-Pillar Architecture)                        │
 │  - HermesDesktopAgent (Win32 Foreground, Clipboard Typing, Coordinate) │
 │  - HermesGeneralAgent (Multi-Step Function Calling across 69 tools)    │
 │  - ImageGeneratorService (Imagen 3 / Pollinations AI / Caching)        │
 │  - Truthful ToolRegistry (69 Executable System Tools)                  │
 │  - LongHorizonCheckpointService (data/jarvis.db SQLite WAL)            │
 │  - KVCachePruner <--> LLMService                                       │
 │  - MobileAuthService (Fail-Closed JWT & Ed25519 Gatekeeper Interlock)  │
 └────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Unified Tool Registry Specification (69 Registered Tools)

All executable actions are dispatched through the centralized `ToolRegistry` (`backend/services/tool_registry.py`), audited by `SafetyGatekeeper`, and executed asynchronously with verification. The 69 executable tools span:

| Category | Count | Primary Tools |
|---|:---:|---|
| **System & OS Control** | 6 | `open_application`, `close_application`, `lock_pc`, `take_screenshot`, `get_system_status`, `toggle_live_mode` |
| **Filesystem & Indexing** | 5 | `search_files`, `read_file_content`, `write_file_content`, `list_directory`, `get_file_metadata` |
| **Web & Research** | 6 | `web_search`, `browser_agent_task`, `browser_navigate`, `browser_click`, `browser_type`, `browser_extract_text` |
| **Automation & UI Perception** | 6 | `click_element_by_name`, `set_control_value`, `auto_fill_form`, `resize_window`, `execute_rpa_macro`, `press_hotkey` |
| **Live Mode & Failover** | 2 | `live_mode_execute_task`, `live_mode_emergency_stop` |
| **Hermes Dual-Agent & Bridge** | 5 | `hermes_bridge_task`, `hermes_async_task`, `hermes_agent_task`, `hermes_orchestrator_task`, `desktop_agent_task` |
| **Memory & Knowledge (RAG)** | 6 | `rag_knowledge_search`, `save_fact`, `query_memory`, `delete_memory`, `explain_concept`, `generate_quiz` |
| **Integrations & Workflows** | 14 | 6x `n8n_*` workflow tools, 4x `gmail_*` & `google_calendar_*` tools, 4x `outlook_*` tools |
| **Security & Proximity** | 2 | `get_proximity_telemetry`, `configure_proximity_lock` |
| **Learning & Productivity** | 6 | `take_note`, `list_notes`, `search_notes`, `draft_copy`, `generate_docstrings`, `analyze_sentiment` |
| **Multimodal & Science** | 11 | `generate_image`, `synthesize_voice`, `list_available_voices`, `generate_audio_effect`, `parse_chemical_formula`, `balance_chemical_equation`, `query_pubchem_compound`, `explain_biological_process`, `critique_ui_layout`, `generate_color_palette`, `scaffold_web_app` |

---

## 4. Production Benchmarks & Performance Metrics (Audited & Verified)

Empirically measured runtime performance on host Windows 11 machine:

| Pipeline Stage | Component / Target | Empirical Latency | Operational Notes |
|---|---|:---:|---|
| **Deterministic Intent Classification** | `FastIntentRouter.classify()` | **0.0083 ms** | In-memory compiled regex triage |
| **Speech-to-Text (STT)** | Faster-Whisper (CUDA) | **704.2 ms** | Real spoken audio chunk transcription |
| **Atomic Desktop Tool Execution** | `open_application` / `psutil` | **17.5 ms** | Sub-20ms OS process invocation |
| **Action Verification** | `ActionExecutionVerifier` | **27.3 ms** | Native in-memory `psutil` inspection |
| **Failover Control Lock Handshake** | `LiveModeFailoverSupervisor` | **<1.5 ms** | In-memory `asyncio.Lock()` acquisition and state transition |
| **World Model Refresh** | `WorldModel.refresh()` | **2.86 ms** | Real-time UIA scene graph & Win32 cursor capture |
| **Speech Synthesis (TTS Tier 1-3)** | Edge-TTS / Piper ONNX / SAPI SpVoice | **213.1 ms** (SAPI) | Automatic 3-tier fallback |
| **Total Voice-to-Action Pipeline** | Audio In → Action Execution | **870.6 ms** | Sub-second real-time responsiveness |
| **Total Registered System Tools** | `ToolRegistry` | **69 Tools** | Fully audited, safety-gated, and verified |
| **Master Test Suite** | 30 Test Files (`backend/tests/`) | **298/298 Passed** | 100% pass rate in ~216s |

---

## 5. Technical Specifications for Multimodal, Failover & Hermes Expansion (Added September 2026)

### 1. Live Mode Failover Controller
- **Module**: `backend/services/live_mode/failover_controller.py`.
- **Authority States**: `PRIMARY_ACTIVE`, `FAILOVER_PENDING`, `HERMES_ACTIVE`, `RECOVERY`, `COMPLETED`, `FAILED`, `CANCELLED`.
- **Mutual Exclusion**: `_control_lock = asyncio.Lock()` guarantees primary and fallback agents never issue conflicting inputs.
- **Failover Payload**: Primary transfers `(completed_steps, failed_step, error_reason, screen_context)` enabling Hermes to resume without repeating work.

### 2. 12-Pillar Hermes Bridge Architecture
- **Module**: `backend/services/hermes_bridge.py`.
- **Capabilities**: Tool execution, agent orchestration, command routing, computer control bridge, task automation, background worker queue, context sync, local dev daemon, extensibility, error boundary, permission boundaries, and WebSocket telemetry streaming.
- **Dual Agents**:
  - `HermesDesktopAgent` (`backend/agents/desktop_agent.py`): Windows 11 foregrounding via `AttachThreadInput`, clipboard typing (`Ctrl+V`), and coordinate clicks.
  - `HermesGeneralAgent` (`backend/agents/hermes_agent.py`): Multi-step LLM function calling orchestrator across all 69 system tools.

### 3. In-Chat Image Generation Engine
- **Module**: `backend/services/image_generator.py`.
- **Providers**: Google Imagen 3 (primary) with Pollinations AI fallback.
- **Disk Caching**: Images cached in `data/generated_images/` with UUID-based filenames and served through FastAPI static mount.
- **UI Lightbox**: Integrated into `ChatPanel.tsx` with pan, zoom, copy, and download actions.




