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

## 3. Unified Tool Registry Specification (33 Registered Tools)

All executable actions are dispatched through the centralized `ToolRegistry` (`backend/services/tool_registry.py`), audited by `SafetyGatekeeper`, and executed asynchronously with verification:

| Category | Count | Tools |
|---|:---:|---|
| **Automation & UI Perception** | 4 | `click_element_by_name`, `set_control_value`, `auto_fill_form`, `resize_window` |
| **System & OS Controls** | 6 | `open_application`, `close_application`, `lock_pc`, `take_screenshot`, `get_system_status`, `toggle_live_mode` |
| **Web & Research** | 2 | `web_search`, `browser_agent_task` |
| **Media & Entertainment** | 2 | `play_youtube_video`, `media_control` |
| **Knowledge & Learning** | 3 | `rag_knowledge_search`, `explain_concept`, `generate_quiz` |
| **n8n Workflow Automation** | 6 | `n8n_list_workflows`, `n8n_get_workflow`, `n8n_execute_workflow`, `n8n_create_workflow`, `n8n_activate_workflow`, `n8n_deactivate_workflow` |
| **Cloud & Workspace** | 8 | `gmail_list_messages`, `gmail_send_message`, `google_calendar_list_events`, `google_calendar_create_event`, `outlook_list_messages`, `outlook_send_message`, `outlook_calendar_list_events`, `outlook_calendar_create_event` |
| **Security & Proximity** | 2 | `get_proximity_telemetry`, `configure_proximity_lock` |

