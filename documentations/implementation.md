# 🏗️ Implementation Architecture & Component Breakdown

This document provides a deep dive into the code structure, file layouts, startup execution sequence, and background services in JARVIS.

---

## 1. Project Directory Structure

```
JARVIS/
├── backend/
│   ├── api/
│   │   ├── routes/          # REST endpoints (health, status, history, settings, etc.)
│   │   └── websockets.py    # Main WebSocket duplex router (/api/voice)
│   ├── agents/
│   │   ├── langgraph_agent/ # New LangGraph agent module (state, tools, nodes, state machine)
│   │   ├── multi_agent/     # CEO-Planner-Worker orchestrators [NEW]
│   │   ├── context_manager.py # Shared Agent Context manager [NEW]
│   │   ├── planner.py       # Central agent that runs LangGraph agent or fallback router
│   │   ├── subagent.py      # Base class for specialized worker agents
│   │   └── voice.py         # Handles voice stream loop processing
│   ├── models/
│   │   ├── database.py      # Async SQLAlchemy SQLite model classes
│   │   └── schemas.py       # Pydantic validation models
│   ├── mcp/                 # Model Context Protocol layer [NEW]
│   │   ├── servers/         # Local MCP servers (e.g. file_server.py)
│   │   ├── client.py        # MCPServerConnection and MCPClientManager
│   │   └── protocol.py      # Compliant JSON-RPC 2.0 helper
│   ├── services/
│   │   ├── security/        # Sandboxes & Encrypted vault [NEW]
│   │   │   ├── vault.py     # Local AES encrypted file + Windows Credential Vault
│   │   │   ├── sandbox.py   # Subprocess limits & resource-bounded executors
│   │   │   └── rbac.py      # Security approvals and audit logging
│   │   ├── plugins/         # Plugins loader framework [NEW]
│   │   ├── automation.py    # pywinauto and PyAutoGUI GUI automation
│   │   ├── browser.py       # Playwright browser manager
│   │   ├── clap.py          # Background microphone clap listener
│   │   ├── config_manager.py # Config hot-reloader [NEW]
│   │   ├── hybrid_memory_system.py # 6-Scope memory graph builder [NEW]
│   │   ├── rag_service.py   # PDF/DOCX/PPTX RAG matching pipelines [NEW]
│   │   ├── llm.py           # Model bindings wrapper for APIs & local Ollama
│   │   ├── llm_router.py    # Metric analyzer & fallback router
│   │   ├── manager.py       # ServiceManager lifecycle registry [NEW]
│   │   ├── base.py          # BaseService modular interface [NEW]
│   │   ├── memory.py        # SQLite + ChromaDB semantic cache
│   │   ├── redis_cache.py   # Hybrid in-memory & Redis cache manager
│   │   ├── gpu_scheduler.py # CUDA VRAM scheduler & lazy model loader
│   │   ├── observability.py # Distributed trace IDs & system health telemetry
│   │   ├── cross_platform.py # OS abstraction layer & companion mobile sync broker
│   │   ├── test_runner.py   # Performance benchmarks & local ZIP backup manager
│   │   ├── autonomous_engine.py # Habit learning, predictive tasks & goal planner
│   │   ├── safety.py        # Banned keyword & command safety checks
│   │   ├── screen.py        # Screenshot capturing & vision API
│   │   ├── stt.py           # faster-whisper local STT engine
│   │   ├── tts.py           # edge-tts voice synthesis engine
│   │   └── wake_word.py     # Local openwakeword wake word pipeline
│   ├── utils/
│   │   ├── logger.py        # Loguru console/file logging & EventBus hooks
│   │   ├── event_bus.py     # Wildcard async topic EventBus [NEW]
│   │   └── task_queue.py    # Sequential asyncio Task Queue [NEW]
│   ├── config.py            # Centralized settings loader (Pydantic Settings)
│   └── main.py              # Application server entry point (FastAPI)
│
├── frontend/
│   ├── src/
│   │   ├── main/            # Electron main process (spawns backend, manages window)
│   │   ├── preload/         # IPC bridge script
│   │   └── renderer/        # React 19 visual application
│   │       ├── src/
│   │       │   ├── components/  # DashboardLayout, HardwareGauges, LLMProvidersCard, AgentOrchestratorCard, ComputerUseCard, BrowserAutomationCard, WorkflowManagerCard, MemoryGraphCard, KnowledgeHubCard, MCPServersCard, CommandPalette, Orb, ChatPanel, VoiceWave, Settings, TitleBar
│   │       │   ├── hooks/       # WebSocket hooks, key listeners
│   │       │   ├── lib/         # Three.js WebGL (orbScene) and MediaPipe (handTracker)
│   │       │   ├── stores/      # Zustand state engines
│   │       │   └── index.css    # Tailwind styles and keyframes
│   └── package.json         # Build configuration and scripts
│
├── .env                     # Configuration credentials (loaded at startup)
├── setup.bat                # Automated node and python workspace installer
└── start.bat                # Automated application startup script
```

---

## 2. Boot & Startup Sequence

When a user double-clicks `start.bat` (or runs `npm run dev` in the frontend directory):

```
[start.bat]
   │
   └──► Clear ELECTRON_RUN_AS_NODE (Prevents VS Code terminal issues)
   └──► Launch Electron main process (frontend/src/main/index.ts)
           │
           ├──► 1. Read config, launch loading screen window
           ├──► 2. Spawn python backend as sub-process:
           │       "venv\Scripts\python.exe backend\main.py"
           │       (Redirects logs to Electron stdout)
           │
           └──► 3. Wait for backend health check endpoint (/api/health) to return status 200
                   │
                    ├───► [FastAPI Backend Startup]
                    │        ├──► 1. Initialize Event Bus, Context Manager & sequential AsyncTaskQueue
                    │        ├──► 2. Initialize Security Vault, constrained Sandbox & RBAC orchestrators
                    │        ├──► 3. Initialize dynamic MCP Client Manager & local FastMCP subprocesses
                    │        ├──► 4. Initialize Hybrid Memory Graph (NetworkX) & RAG semantic directories
                    │        ├──► 5. Initialize DB schemas (SQLite / aiosqlite) & ChromaDB vector workspace
                    │        ├──► 6. Spin up ClapService background thread and register uvicorn server on port 8000
                    │
                    └───► 4. Close loading screen, launch main visual window
```

---

## 3. Core Background Workers

### 3.1. Clap Service (`backend/services/clap.py`)
* **Execution**: Runs in a separate, dedicated native thread (`threading.Thread`) started during the backend boot lifecycle.
* **Mechanism**:
  1. Opens an audio input stream using `PyAudio` (listening on the default Windows audio device).
  2. Analyzes audio buffers in real-time, calculating energy levels.
  3. When an energy peak exceeds a dynamic threshold, starts a timer window. If a second peak is observed within the time window (`0.1s` - `0.5s`), it registers a double-clap event.
  4. Dispatches the event via HTTP request/WebSocket message to Electron to execute morning workflows.

### 3.2. Wake Word Pipeline (`backend/services/wake_word.py`)
* **Execution**: Activated only when the assistant state is `idle`.
* **Mechanism**:
  1. Utilizes a Python generator that yields chunks from the micro-stream.
  2. Forwards features into `openwakeword` models.
  3. If a model output passes the sensitivity threshold (e.g. `0.5`), yields a wake event.

### 3.3. Audio Stream Queue (`backend/services/voice.py`)
* **Execution**: An asynchronous task loop queue (`asyncio.Queue`) that serializes outgoing TTS audio segments.
* **Mechanism**:
  1. Prevents voice overlaps by prioritizing speech streams.
  2. Supports instant interrupts: If the user begins speaking while JARVIS is talking, the client sends a socket cancel event. The backend immediately purges the active TTS queue and terminates active playback.

### 3.4. Local Hand Gesture Tracker (`frontend/src/renderer/src/lib/handTracker.ts`)
* **Execution**: Activated only when the camera state is `on`. Evaluates video frames on every `requestAnimationFrame` tick.
* **Mechanism**:
  1. Captures webcam buffers from `getUserMedia` video tracks.
  2. Resolves MediaPipe WASM tasks resolver and downloads float16 landmark models locally.
  3. Parses frames in memory, extracting NormalizedLandmarks for skeletal joint connections.
  4. Triggers rotate/zoom callbacks to modify the Three.js viewport controls.

---

## 4. Subagent Implementations

When the `PlannerAgent` (`backend/agents/planner.py`) determines that a query requires complex execution, it constructs an plan of `AgentSteps` and executes them using specialized libraries:

### 4.1. Automation Service (`backend/services/automation.py`)
* **Libraries**: `pywinauto` (controls native Windows application windows) and `PyAutoGUI` (handles pixel-based mouse coordinates, drag-and-drops, and keystrokes).
* **Usage**: Focuses specific window titles (e.g. Chrome, Spotify), types text templates, inputs system-level hotkeys (e.g. `Ctrl+Alt+Tab`), and performs desktop actions:
  * **Minimize Window**: Searches for active window handles matching a title or app name and minimizes them using `win.minimize()`.
  * **Absolute Volume Set**: Sets system speaker volume to an exact percentage (0-100%) by zeroing out the master volume first (50 presses of `volumedown`) and then pressing `volumeup` in 2% steps up to the target level.

### 4.2. Browser Service (`backend/services/browser.py`)
* **Library**: `Playwright` (Chromium engine).
* **Usage**: Headless navigation, scrolling, reading selectors, clicking buttons, submitting text input forms, and scraping articles.

### 4.3. Screen Service (`backend/services/screen.py`)
* **Libraries**: `pyautogui.screenshot()` for capturing displays. `pytesseract` for local OCR translation.
* **Usage**: Captures screen images, encodes them to base64, and dispatches them to multimodal models (`Gemini-2.0-Flash` / `GPT-4o`) to answer queries about active developer workflows or errors.

### 4.4. LangGraph Tool Calling Agent (`backend/agents/langgraph_agent/`)
* **Libraries**: `langgraph`, `langchain-core`
* **Structure**:
  - `state.py`: TypedDict state definition representing the agent conversation steps and execution tracking.
  - `tools.py`: Custom registered LangChain tools (CMD execution with confirmation flags, Python interpreter running, File System operations, User Input prompts, SQLite key-value Memory, and Playwright Web Search).
  - `nodes.py`: Node functions executing graph logic (Prash routing, Planning steps, Tool Selection/Execution, and summary generation).
  - `agent.py`: Compiles the workflow StateGraph and exposes a generator that streams log states.
* **Routing**: Prash acts as the primary local AI decider. If Prash's output entropy exceeds the confidence threshold, the agent transitions state to `fallback` and delegates the prompt directly to the Ollama → GPT → Gemini fallback cascade.
