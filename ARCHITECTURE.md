# 🏛️ ARCHITECTURE — JARVIS Personal AI Operating System

This document describes the runtime architecture, perception flow, local AI engine routing, self-healing pipeline, and safety interlocks of the **JARVIS Personal AI OS**.

---

## 📐 System High-Level Architecture

```mermaid
graph TD
    User([User Voice / GUI / Mobile]) --> Frontend[Electron / React 19 Desktop HUD]
    User --> Mobile[Android Companion App]
    
    Frontend <--> |WebSocket / REST| FastAPI[FastAPI Monolith Backend]
    Mobile <--> |WebSocket / REST| MobileRouter[Mobile Gateway Router & Security Gatekeeper]
    
    FastAPI --> WorldModel[World Model State Aggregator]
    WorldModel --> UIA[Win32 UIA Scene Graph Parser]
    WorldModel --> Spatial[Spatial Engine & Display Resolution]
    WorldModel --> WsIntel[Workspace Intelligence Service]
    
    FastAPI --> UnifiedPipeline[10-Step Unified Pipeline]
    UnifiedPipeline --> Prash[Prash Local AI Engine (Transformer)]
    Prash -- "High Entropy Fallback" --> LLM[Cloud LLM Cascade: Ollama / Gemini / Groq / OpenAI]
    
    UnifiedPipeline --> ToolReg[Tool Registry & Skill Modules]
    ToolReg --> Safety[Security Sandbox & Mobile Approval Interlock]
    ToolReg --> Auto[Automation Service: pywinauto / Popen]
    
    UnifiedPipeline --> ExpEngine[Experience Engine (experiences.db)]
    ExpEngine --> Reflection[Reflection Engine (Failure Evaluation)]
    Reflection --> StratMemory[Strategy Memory (strategy_memory.json)]
```

---

## 🧩 Core Architectural Subsystems

### 1. Central Perception (`WorldModel` & `UIASceneGraph`)
- **Sub-30ms State Aggregation**: `WorldModel` thread-safely aggregates active window titles, process IDs, connected display monitor bounds, clipboard text, WASAPI audio activity, and internet connectivity.
- **Native Win32 Control Tree (`UIASceneGraph`)**: Uses `pywinauto.uia_element_info` to parse native Windows controls (buttons, textboxes, form fields, menus, dialogs) into structured scene graphs without visual OCR overhead.
- **Workspace Intelligence (`WorkspaceIntelligenceService`)**: Infers active project name, operational goal, session workflow (`coding`, `research`, `study`), 20-action ring buffer, and habit transition predictions persisted to `data/user_habits.json`.

### 2. Local AI Reasoning (`PrashEngine`)
- **Primary Execution Engine**: Local Transformer model (`data/prash`) evaluating token prediction entropy.
- **Entropy Confidence Gate**: Low entropy (<= 3.0 Shannon entropy) returns instant local responses. High entropy (> 3.0) triggers explicit, logged handoff to secondary cloud cascades.
- **Uniform Prompt & Tool Context**: Both Prash local engine and cloud LLMs receive identical tool schemas (`TOOL_DEFINITIONS`), World Model desktop context, and conversation history.

### 3. Unified 10-Step Self-Improving OS Lifecycle (`UnifiedPipeline`)
Every user command undergoes a 10-stage execution pipeline:
1. **Perception**: Capture `WorldModel` state.
2. **Strategy Memory Lookup**: Retrieve strategy success weights from `strategy_memory.json`.
3. **Intent Detection**: Classify command category (automation, system, query, workflow).
4. **Planning**: Construct step-by-step execution plan (`PlannerAgent`).
5. **Tool Resolution**: Match plan steps against `ToolRegistry`.
6. **Safety Verification**: Inspect command for destructive patterns (`SecuritySandbox`).
7. **Execution**: Invoke automation handlers or open interactive terminal scripts.
8. **Observation**: Read stdout/stderr or verify visual window state changes.
9. **Reflection**: Evaluate execution outcome (`ReflectionEngine`).
10. **Experience Recording**: Log trace to SQLite-WAL (`experiences.db`) and update `StrategyMemory`.

### 4. Interactive Safety Interlocks & Mobile Gatekeeper
- **Destructive Command Guard**: Commands containing `del`, `rmdir`, `format`, `shutdown`, `reboot` require explicit confirmation.
- **Desktop Exit Interlock**: Window close ('X') or application shutdown triggers a signed approval request via `MobileGatewayService` to the paired Android companion app and renders a desktop `SafetyPermissionModal.tsx`.

---

## 📂 Key Codebase Directories

```
backend/
├── agents/             # Planner, Message Router, LangGraph Agent, Unified Pipeline
├── api/                # REST endpoints (routes.py, mobile_router.py, debug_router.py, mobile_ws.py)
├── models/             # Pydantic schemas & SQLAlchemy ORM models
├── services/           # Core OS services
│   ├── live_mode/      # Live Mode engine & Form Assistant
│   ├── perception/     # UIA Scene Graph, Spatial Engine, Spatial Ref Parser
│   ├── prash/          # Prash Local AI Engine & Tokenizer
│   ├── security/       # Security Sandbox & Safety Service
│   ├── skills/         # Modular skill tools (Learning, Automation, Dev, Research, Voice)
│   ├── automation.py   # Desktop automation, app launch & Python script launcher
│   ├── world_model.py  # Central World Model aggregator
│   └── workspace_intelligence.py # Workspace context, goals & habit predictor
data/                   # Persistent SQLite databases, vector stores & JSON habit matrices
frontend/               # Electron + React 19 + Tailwind CSS desktop app
```
