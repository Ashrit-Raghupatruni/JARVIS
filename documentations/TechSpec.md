# 📐 Technical Specification (TechSpec)

This document provides the high-level technical specifications, stack requirements, component boundaries, and performance benchmarks for JARVIS. **Last Updated:** August 8, 2026

---

## 1. Technology Stack Specification

| Layer | Technologies & Frameworks |
|---|---|
| **Frontend Framework** | React 18, TypeScript 5, Vite, Electron 30, TailwindCSS, Lucide Icons |
| **3D Render Engine** | Three.js (r164), WebGL 2, `GLTFLoader`, `MeshoptDecoder`, Custom PBR Shaders |
| **3D Asset** | `facecap.glb` (332.8 KB, Three.js dev examples) with ARKit morph targets |
| **Backend Core** | Python 3.10, FastAPI, Uvicorn, Asyncio Event Loop, Loguru |
| **Database** | SQLite3 with WAL (Write-Ahead Logging) and FTS5 Full-Text Search |
| **Agent Ecosystem** | `AgentEcosystemService`, `SubAgentInstance`, `LongHorizonCheckpointService`, `KVCachePruner` |
| **Security & Auth** | PyJWT (`HS256`), `SafetyService` Regex Policy Engine, Gatekeeper Mobile Interlock |

---

## 2. Component Boundaries & API Interconnects

```
 ┌────────────────────────────────────────────────────────────────────────┐
 │                      React / Electron Renderer                         │
 │  - Hero Visualizer (IdleHUD.tsx / TalkingFace3D.tsx)                   │
 │  - Nav Bar (☰ Command Center ▾ Dropdown)                               │
 │  - AutonomousAgentStudio.tsx (Sub-agents, IPC logs, Goals, Pruner)     │
 └───────────────────────────────────┬────────────────────────────────────┘
                                     │ WebSocket / REST API
 ┌───────────────────────────────────▼────────────────────────────────────┐
 │                          FastAPI Backend Core                          │
 │  - ServiceManager Registry                                             │
 │  - AgentEcosystemService <--> SubAgentInstance <--> PlannerAgent      │
 │  - LongHorizonCheckpointService (data/jarvis.db SQLite WAL)            │
 │  - KVCachePruner <--> LLMService                                       │
 │  - MobileAuthService (Fail-Closed JWT & Gatekeeper Interlock)          │
 └────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Unified Tool Registry Specification (61 Registered Tools)

All executable actions are dispatched through the centralized `ToolRegistry` (`backend/services/tool_registry.py`), audited by `SafetyGatekeeper`, and executed asynchronously with verification. The 61 executable tools span:

| Category | Count | Primary Tools |
|---|:---:|---|
| **System & OS Control** | 6 | `open_application`, `close_application`, `lock_pc`, `take_screenshot`, `get_system_status`, `toggle_live_mode` |
| **Filesystem & Indexing** | 5 | `search_files`, `read_file_content`, `write_file_content`, `list_directory`, `get_file_metadata` |
| **Web & Research** | 6 | `web_search`, `browser_agent_task`, `browser_navigate`, `browser_click`, `browser_type`, `browser_extract_text` |
| **Automation & UI Perception** | 6 | `click_element_by_name`, `set_control_value`, `auto_fill_form`, `resize_window`, `execute_rpa_macro`, `press_hotkey` |
| **Memory & Knowledge (RAG)** | 6 | `rag_knowledge_search`, `save_fact`, `query_memory`, `delete_memory`, `explain_concept`, `generate_quiz` |
| **Integrations & Workflows** | 14 | 6x `n8n_*` workflow tools, 4x `gmail_*` & `google_calendar_*` tools, 4x `outlook_*` tools |
| **Security & Proximity** | 2 | `get_proximity_telemetry`, `configure_proximity_lock` |
| **Learning & Productivity** | 6 | `take_note`, `list_notes`, `search_notes`, `draft_copy`, `generate_docstrings`, `analyze_sentiment` |
| **Multimodal & Science** | 10 | `synthesize_voice`, `list_available_voices`, `generate_audio_effect`, `parse_chemical_formula`, `balance_chemical_equation`, `query_pubchem_compound`, `explain_biological_process`, `critique_ui_layout`, `generate_color_palette`, `scaffold_web_app` |

---

## 4. Production Benchmarks & Performance Metrics (Audited & Verified)

Empirically measured runtime performance on host Windows 11 machine:

| Pipeline Stage | Component / Target | Empirical Latency | Operational Notes |
|---|---|:---:|---|
| **Deterministic Intent Classification** | `FastIntentRouter.classify()` | **0.0083 ms** | In-memory compiled regex triage |
| **Speech-to-Text (STT)** | Faster-Whisper (CUDA) | **704.2 ms** | Real spoken audio chunk transcription |
| **Atomic Desktop Tool Execution** | `open_application` / `psutil` | **17.5 ms** | Sub-20ms OS process invocation |
| **Action Verification** | `ActionExecutionVerifier` | **27.3 ms** | Native in-memory `psutil` inspection |
| **World Model Refresh** | `WorldModel.refresh()` | **2.86 ms** | Real-time UIA scene graph & Win32 cursor capture |
| **Speech Synthesis (TTS Tier 1-3)** | Edge-TTS / Piper ONNX / SAPI SpVoice | **213.1 ms** (SAPI) | Automatic 3-tier fallback |
| **Total Voice-to-Action Pipeline** | Audio In → Action Execution | **870.6 ms** | Sub-second real-time responsiveness |
| **Total Registered System Tools** | `ToolRegistry` | **61 Tools** | Fully audited, safety-gated, and verified |
| **Master Test Suite** | 12 Test Files (`backend/tests/`) | **116/116 Passed** | 100% pass rate in ~23s |

---

## 5. Technical Specifications for Multimodal & Domain Expansion (Added September 8, 2026)

### 1. Asynchronous Multimodal Generation Queue Architecture
- **Job Engine**: `AsyncGenerationJobManager` in `backend/services/async_generation_queue.py`.
- **Database Table**: `generation_jobs` in `data/generation_jobs.db` (`SQLite WAL` mode) storing `job_id`, `media_type`, `prompt`, `status`, `progress`, `file_path`, `error`, `created_at`, `updated_at`.
- **Worker Concurrency**: Async background tasks managed via `asyncio.create_task` with mutex protection.
- **Fail-Closed Adapters**:
  - Image: Local Torch SDXL/SD1.5 (requires CUDA GPU) or Stability AI REST API.
  - Video: Local SVD (requires CUDA GPU) or Runway REST API.
  - 3D: Procedural Three.js GLTF generator + Meshy/Tripo3D cloud REST API.

### 2. Specialized Task Engines
- **Prompt Transformation Engine**: `backend/services/prompt_pipeline.py` (Rule-based heuristics + AST-tokenized transformations for sub-5ms summarization, style transfer, and entity extraction).
- **Science & Chemoinformatics Engine**: `backend/services/science_service.py` (Deterministic regex formula tokenizer, stoichiometry balancer, NCBI PubChem REST client via `urllib.request`).
- **Design Assistant & Scaffolder**: `backend/services/design_assistant.py` (WCAG 2.1 luminance contrast formula evaluation, Tailwind CSS token builder, standalone React component generator).
- **Vision Intelligence Engine**: `backend/services/vision_service.py` (OpenCV `CascadeClassifier` + contour area segmentation and grounded caption generator).
- **Developer Assistant**: `backend/services/developer_assistant.py` (Python `ast` module parser for docstring generation and SQL AST parser rejecting unsafe mutations).
- **Productivity Service**: `backend/services/productivity_service.py` (Markdown file I/O with frontmatter parsing in `data/notes/`, multi-channel copy synthesis).



