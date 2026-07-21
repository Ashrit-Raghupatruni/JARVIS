# JARVIS — Comprehensive Status, Tech Stack, & Features Overview

This document serves as the single source of truth for JARVIS's current capabilities, system architecture, tech stack, and development status.**Last Updated:** July 17, 2026

---

## 📋 Tech Stack

The architecture is split into a **React + Electron** desktop client (frontend) and a **FastAPI + WebSockets** backend service (Python).

### Frontend (Desktop Client)
* **Shell/Container:** Electron v35.0.0 (manages OS-level desktop windows, system tray, global shortcut registration)
* **Framework:** React v19.1.0 + TypeScript v5.8.0 + Vite v6.3.0
* **Build System:** `electron-vite` v3.1.0 + `electron-builder` v25.1.0
* **Styling:** Tailwind CSS v4.1.0 + `@tailwindcss/vite`
* **State Management:** Zustand v5.0.0
* **3D Visuals:** Three.js v0.185.1 (WebGL rendering of a procedural 3D Arc Reactor model including gear-notched outermost ring, ticking LED points, segmented step ring, radial copper coils, and central glow bulb cores, with stardust fields, orbiting satellites, sweeping scan rings, and chromatic aberration shader passes)
* **Gesture Tracking:** MediaPipe Tasks-Vision v0.10.35 (local hand landmark calculations to trigger viewport camera rotations and zoom levels)
* **Communication:** Native WebSockets for real-time bidirectional status, audio stream, and command events

### Backend (Python Service)
* **Core Web Server:** FastAPI v0.115.9 + Uvicorn v0.34.2 (runs locally on port 8000)
* **Database (Relational):** SQLite + SQLAlchemy ORM v2.0.41 + `aiosqlite` v0.21.0 (non-blocking async transactions)
* **Database (Vector):** ChromaDB v1.0.7 (vector storage for semantic long-term memory)
* **Embeddings Model:** `sentence-transformers` v4.1.0 (runs `all-MiniLM-L6-v2` locally for context matching; falls back to default ChromaDB embeddings on failure)
* **Task Scheduling:** Background tasks run asynchronously inside FastAPI lifespan context
* **Utilities:** `loguru` v0.7.3 (structured logging), `python-dotenv` v1.1.0 (config management)

### AI Models & Integrations
* **Prash Local AI Engine:** A custom, decoder-only 0.70M-parameter Transformer model trained on a GPU (T4 in Google Colab) using a synthetic conversational command dataset.
  * **Direct BPE Token Formatting:** Resolves startup formatting mismatches by compiling prompt logs into direct token ID sequences (`<BOS> query <SEP>`) matching the exact BPE tokenizer rules.
  * **Intelligent Routing Node:** Classifies user query confidence based on token prediction entropy. Conversational intents are spoken directly; system-control actions trigger the tool planner node; low-confidence queries route directly to the cloud fallback cascade.
* **LLM Engine & Intelligent Router:** Multi-provider orchestration client supporting Ollama, Google Gemini, Groq, OpenAI, and OpenRouter:
  * **Dynamic Ranking Router:** Auto-measures response times, first-token latency, completion speed, success rate, cost, and quality to rank available models in real time. Runs a background poller thread with a circuit-breaker (trips after 3 consecutive failures).
  * **Resilient Tool Fallbacks:** Parameter-validation try-catch blocks automatically and silently retry requests without tools if a model-specific error occurs (e.g. Groq's formatting failure) or if tool calling is unsupported.
  * **Gemini Pydantic Integration:** Maps conversation history using native `types.Content` and `types.Part` SDK objects to satisfy strict Pydantic 2.x validation.
* **Speech-to-Text (STT):** Local `faster-whisper` v1.1.1 (based on CTranslate2 base/small model) with automated API failover to Gemini Audio API or OpenAI Whisper API
* **Text-to-Speech (TTS):** Microsoft `edge-tts` v7.2.8 (local/online hybrid, restricted to male-only voices: `en-GB-RyanNeural`, `en-US-GuyNeural`, `en-AU-WilliamNeural`, `en-IN-PrabhatNeural`) + ElevenLabs v1.50 (optional premium API)
* **Wake Word:** `openwakeword` v0.6.0 (running ONNX runtime for local "Hey Jarvis" keyword trigger)
* **Hand Gesture Tracker:** Local `MediaPipe Hand Landmarker` model executing in browser sandbox to evaluate raw webcam feeds, mapping single pinch coordinates to Orbit camera rotations and double pinch spread intervals to zoom factors.

---

## 🛠️ Architecture & Major Modules

```
                             ┌──────────────────────────────────┐
                             │        ELECTRON FRONTEND         │
                             │   (React 19, Zustand, UI Orb)    │
                             └────────────────┬─────────────────┘
                                              │ (WebSocket port 8000)
                                              ▼
                             ┌──────────────────────────────────┐
                             │         FASTAPI BACKEND          │
                             └────────────────┬─────────────────┘
                                              │
         ┌───────────────────────────┬────────┴───────────────────┬──────────────────────────┐
         ▼                           ▼                           ▼                          ▼
┌───────────────────┐       ┌───────────────────┐       ┌───────────────────┐      ┌───────────────────┐
│   VOICE AGENT     │       │   PLANNER AGENT   │       │   SYNC SERVICE    │      │   CLAP LISTENER   │
│ - Wake Word       │       │ - Tool Execution  │       │ - UDP Heartbeats  │      │ - sounddevice RMS │
│ - Mic Audio Loop  │       │ - Skill Registry  │       │ - AES WebSocket   │      │ - Welcome Flow    │
└───────────────────┘       └───────────────────┘       └───────────────────┘      └───────────────────┘
```

### 1. Voice Agent Pipeline (`backend/agents/voice.py`)
Coordinates microphone recording, wake word detection, STT transcription, LLM command execution, and TTS playback. It manages the following state machine transitions:
* `idle` ⇄ `listening` ⇄ `processing` ⇄ `speaking` ⇄ `executing`
* Supports **Push-to-Talk (PTT)** (shortcut `Ctrl + Space` triggered from Electron via `onPushToTalk`) and wake-word activation.
* Sends real-time binary audio packets (16kHz PCM) and interrupts speaking playback instantly upon receiving an `interrupt` command.

### 2. Planner Agent (`backend/agents/planner.py`)
Central orchestrator that coordinates natural language parsing, tool selection, and execution steps.
* Runs LLM completions with dynamic tool definitions.
* Integrates the `PrashLangGraphAgent` state machine workflow for tool calling.
* Spawns multi-step plans and streams progress updates (`type="agent_progress"`).
* Integrates thread-safe local history lists to isolate background sub-agents and prevent concurrent runs from corrupting user history.

### 3. Skill Plugin Registry (`backend/services/skills/`)
Implements an extensible plugin architecture where new skills inherit from `BaseSkill` and expose tools decorated with `@skill_tool`. The active skills registered inside `registry.py` are:
* **FileSkill:** Local disk manipulation with duplicate detection (MD5), download folders sorting by type, meeting notes templates, and Recycle Bin safety (`send2trash`).
* **CommunicationSkill:** SMTP/IMAP client, `pywhatkit` WhatsApp triggers, Slack/Discord webhooks, ADB Android integration for calls/SMS, and local SQLite calendar events storage (`calendar.db`).
* **SystemSkill:** CPU/Memory process monitor, `psutil` task manager (process kill), clipboard copy/paste, startup program registries, and WiFi/System power triggers.
* **AppControlSkill:** Excel & Word COM automation (`win32com.client`), VS Code project launcher, and browser tab keystroke macros.
* **ContextSkill:** Active window titles/executables scanner and pomodoro focus session limits.
* **AgentSkill:** Autonomous sub-agent syndicate controller (creates headless async tasks to execute background goals).
* **NewsSkill:** Real-time news & financial RSS aggregator (BBC, CNBC, Bloomberg, Reuters, NYTimes, AlJazeera, MarketWatch), World/Finance Monitor controllers (worldmonitor.app & finance.worldmonitor.app), morning briefings (calendar, weather, system status, news headlines), and deep multi-hop research scraper engine (ported from Friday/OpenJarvis).

### 4. Memory & Database Layer (`backend/services/memory.py` / `backend/models/database.py`)
* **SQLite Database (`data/jarvis.db`):** Houses structured ORM tables:
  * `conversations` & `messages`: Multi-turn chat persistence.
  * `user_preferences`: Key-value configuration.
  * `command_logs` & `task_logs`: Audit logs for desktop automation and multi-step plan steps.
* **ChromaDB Vector Store (`data/chroma_data/`):** Contains semantic collections:
  * `conversations`: Conversation logs for history recall.
  * `knowledge`: User preferences, facts, and synced peer states.

### 5. Double-Clap Listener (`backend/services/clap.py`)
* Listens continuously to the default system microphone for two high-RMS transients spaced between 0.05s and 0.35s apart.
* Tracks adaptive noise floors dynamically to calibrate sensitivity.
* Spawns a customized **Welcome Flow** on trigger:
  * Plays a specified song URL/URI (Spotify or browser).
  * Automatically opens Claude.ai and Binance BTC in separate Chrome windows.
  * Arranges windows on specific monitors (monitors 1 and 3) and fullscreens them.
  * Foregrounds/launches Cursor IDE and activates fullscreen.
  * Synthesizes and speaks a home greeting synthesized via ElevenLabs (cached locally).

### 6. Security Shield (`backend/services/safety.py`)
* **Sensitive Data Redaction:** Runs regex filters to scrub sk- API keys, passwords, and tokens from logging streams.
* **Action Classification:** Flags commands matching destructive keywords (e.g. `rm -rf`, `format C:`, `shutdown`, `reg delete`) as `NEEDS_CONFIRMATION` or `BLOCKED`.
* **Dangerous Tool Interceptor:** Pauses the execution of dangerous tools (`safe_delete`, `kill_process`, `run_terminal_command`, etc.), broadcasts a `permission_request` WebSocket payload, and blocks execution until the user selects "Allow" or "Deny" from the frontend dialog.

### 7. Cross-Device Sync Service (`backend/services/sync_service.py`)
* **Discovery:** Broadcasts UDP heartbeats every 10s on port `18270` advertising local IP and FastAPI server port.
* **Encryption:** Encrypts all packets symmetrically using Fernet (AES-128 in CBC mode) with a shared base64-encoded key (`SYNC_KEY`).
* **WebSocket Syncer:** Opens connections to `/sync` to exchange context state packets (process name, window title, active project) and records merged state updates to the ChromaDB vector database.

---

## 🔌 APIs, Services, and Workflows

### REST API Endpoints
* `GET /health` - Basic uptime and status check.
* `GET /status` - State of all modular services (STT, TTS, Wake Word, LLM, Memory, Screen, Browser).
* `POST /command` - Process text query directly through the voice agent pipeline.
* `GET /history` - Get recent conversation logs from SQLite.
* `POST /settings` - Dynamically update active LLM providers, model names, TTS voice, or rate.
* `GET /voices` - Retrieve available Microsoft edge-tts voices.
* `GET /monitors` - Retrieve list of active display monitors, coordinates, and screen dimensions.

### WebSocket Protocols

#### Assistant Loop (`/ws`)
* **Client to Server Frames:**
  * `push_to_talk_start` / `push_to_talk_stop` - Starts/stops microphone capture.
  * `text_command` - Sends a text command from the chat panel.
  * `audio_data` - Streams raw audio bytes.
  * `interrupt` - Cancels current speech playback immediately.
  * `settings` - Pushes updated display/API settings.
  * `permission_response` - Returns `allowed: true/false` for a pending safety check.
* **Server to Client Frames:**
  * `status` - Updates assistant state (idle, listening, processing, speaking).
  * `transcript` - Returns real-time speech transcription results.
  * `response` - Streams response text.
  * `tts_audio` - Streams synthesized speech MP3 chunks.
  * `agent_progress` - Pushes steps list, description, and completion progress.
  * `permission_request` - Triggers a permission pop-up on the frontend for user confirmation.
  * `subagent_status` - Pushes sub-agent updates (logs, status, progress, final result).

#### Synchronization Tunnel (`/sync`)
* Receives context packets from peer devices, decrypts them, merges values, and writes them to local databases.

---

## ⚙️ Configuration & Environment Variables

These variables are defined in the project's `.env` configuration file:

| Environment Variable | Default Value | Description |
|---|---|---|
| **`LLM_PROVIDER`** | `gemini` | Primary AI engine (`gemini`, `openai`, `ollama`). |
| **`GEMINI_API_KEY`** | *None* | Google Gemini API key. |
| **`GEMINI_API_KEY_ALT`** | *None* | Alternative Google Gemini API key for fallback rotation. |
| **`GEMINI_MODEL`** | `gemini-2.0-flash` | Gemini model name. |
| **`OPENAI_API_KEY`** | *None* | OpenAI API key. |
| **`OPENAI_MODEL`** | `gpt-4o` | OpenAI model identifier. |
| **`OPENROUTER_API_KEY`**| *None* | OpenRouter API Key. |
| **`OPENROUTER_MODEL`**  | `meta-llama/llama-3.3-70b-instruct:free` | OpenRouter model name. |
| **`OLLAMA_BASE_URL`** | `http://localhost:11434`| Local Ollama API server address. |
| **`OLLAMA_MODEL`** | `qwen2.5-coder:3b` | Local Ollama model. |
| **`WHISPER_MODEL`** | `base` | Local Faster-Whisper model size (`tiny`, `base`, `small`, `medium`, `large-v3`). |
| **`WHISPER_DEVICE`** | `auto` | Device for inference (`auto`, `cpu`, `cuda`). |
| **`WHISPER_COMPUTE_TYPE`**| `int8` | Inference quantization (`int8`, `float16`, `float32`). |
| **`TTS_ENGINE`** | `edge-tts` | TTS engine (`edge-tts` or `elevenlabs`). |
| **`TTS_VOICE`** | `en-GB-RyanNeural` | edge-tts voice identifier. |
| **`TTS_RATE`** | `+0%` | edge-tts speech rate shift. |
| **`ELEVENLABS_API_KEY`**| *None* | Premium voice API Key. |
| **`ELEVENLABS_VOICE_ID`**| *None* | Premium ElevenLabs voice ID. |
| **`CLAP_ENABLED`** | `true` | Enables background double-clap listener. |
| **`SYNC_ENABLED`** | `true` | Enables peer device context synchronization. |
| **`SYNC_KEY`** | `U3VwZXJTZWNyZXRLZXlGb3JKQVJWSVMyc3luYw==` | 32-byte symmetric Fernet key base64 string. |
| **`SYNC_PORT`** | `18270` | Peer search UDP port. |
| **`FRIENDLY_DEVICE_NAME`**| `JARVIS Windows` | Device label broadcasted on network. |
| **`WAKE_WORD_THRESHOLD`**| `0.5` | Wake word trigger confidence threshold. |
| **`SAFETY_CONFIRM_DANGEROUS`**| `true` | Requiring approval prompts for destructive tools. |
| **`SAFETY_ALLOW_TERMINAL`**| `true` | Allows running shell commands on host machine. |
| **`DATA_DIR`** | `./data` | persistent storage path (sqlite, calendar, vector db). |

---

## 📦 Dependencies & Purpose

### Python Dependencies (Backend)
* **`fastapi` / `uvicorn` / `websockets`:** Asynchronous web server and WebSocket networking.
* **`openai` / `google-generativeai`:** Integration for OpenAI, OpenRouter, and Google Gemini API clients.
* **`faster-whisper`:** High-performance transcription using quantized CTranslate2 engine.
* **`edge-tts` / `elevenlabs`:** Synthesizes voice waveforms.
* **`openwakeword`:** Local wake-word trigger system.
* **`sounddevice` / `numpy`:** Low-level microphone streaming and RMS math calculations for clap listener.
* **`pyautogui` / `pywinauto` / `pywin32` / `keyboard`:** Controls Windows applications, handles window placement, coordinates, keystrokes, and keyboard hooks.
* **`pytesseract` / `Pillow`:** Tesseract OCR wrapper and PIL images helper.
* **`playwright`:** Headless browser automation.
* **`chromadb` / `sentence-transformers`:** Local vector storage database and semantic text embeddings.
* **`sqlalchemy` / `aiosqlite`:** Async SQLite ORM connection.
* **`cryptography`:** Symmetrically encrypts cross-device synchronization state packets.
* **`send2trash`:** Safe file deletion (moves files to the Recycle Bin instead of deleting permanently).
* **`psutil`:** Inspects processes and monitors system load.
* **`pyperclip`:** Clipboard integration.
* **`pywhatkit`:** Secondary backup helper for WhatsApp web messaging.

---

## ⚙️ Implemented System Architectures & Controls

1. **Contextual Awareness:** Created `ContextSkill` to track active window titles and infer work projects. Integrated background polling checks inside `main.py` every 5 seconds.
2. **Cross-Device Sync:** Added symmetric AES packet encryption (`SyncService`), UDP heartbeats, and WebSocket synchronization routes.
3. **Autonomous Sub-Agents:** Created `SubAgentInstance` background task runner, implemented `AgentSkill` tool definitions (`spawn_subagent`, `get_active_agents`, and `abort_subagent`), and added WebSocket commands to retrieve sub-agent status or cancel tasks dynamically.
4. **Local History Safety:** Refactored conversation history handling inside `PlannerAgent` to utilize concurrent-safe local variables to prevent background agents from corrupting user chat.
5. **Intelligent Router & Self-Improving Brain:** Built a background evaluation loop, active poller, and ChromaDB/SQLite memory manager to rank providers dynamically. Added preference correction extraction to learn from user edits.
6. **Production-Grade Concurrency & Concurrency Verification:** Refactored React custom hooks using a reference-counted WebSocket client singleton to prevent race conditions. Integrated an asynchronous background queue (`voice_queue`) in `websocket.py` to process audio chunks/toggles sequentially and allow instant `interrupt` message parsing.
7. **Session ID Isolation:** Implemented session-level ID tracking in `voice.py` to discard overlapping responses/TTS from stale voice queries when a new voice activation occurs.
8. **Resilient Tool Fallbacks & Parameter Validation:** Wrapped OpenAI, Gemini, Groq, OpenRouter, and NVIDIA NIM completions in catch-all fallbacks to automatically retry without tools on parameter/schema/formatting errors. Corrected `PlannerAgent` to directly await async automation coroutines instead of wrapping them in `asyncio.to_thread`.
9. **3D Visuals & Webcam Gesture Controls:** Replaced flat 2D SVG animations with an interactive, rotating 3D wireframe model of the Arc Reactor (concentric rings, gear teeth, ticking LEDs, and copper coils) fully transparent and floating directly on the app's background. Integrated local MediaPipe hand landmark tracking to control camera rotations/zooms via hand gestures. Added film grain, scanlines, vignette, and a central "J.A.R.V.I.S." overlay in the center of the reactor, while removing the external borders. Designed a drag-vs-click threshold handler to prevent drags from triggering voice prompts.
10. **Holographic HUD, Window Controls & Siri Widget Optimization:**
    * **Non-Blocking Application Launching:** Refactored path resolution in `automation.py` to check for executable existence before launching, enabling fallbacks to Registry and Start Menu searches. Wrapped blocking `os.startfile` operations in `asyncio.to_thread` to prevent thread locks and client timeout errors.
    * **Frameless Resizing Fix:** Removed conflicting `titleBarStyle: 'hidden'` and `titleBarOverlay` properties from the main Electron window creation in `index.ts`, restoring fully functioning custom maximize/restore buttons.
    * **Context-Aware Siri Overlay Popup:** Added window focus checks to inhibit showing the Siri widget when the user is already interacting with the main JARVIS application, hiding it automatically on focus event updates.
    * **Clutter-Free Visuals:** Deleted floating text shortcuts inside the WebGL canvas viewport, making the transparent Arc Reactor floating display clean and focused.
11. **Prash Local AI Engine & LangGraph Agent Integration:**
    * **Prash Local Model**: Deployed a custom 0.70M-parameter Transformer model trained on a T4 GPU (Google Colab) with lowercase BPE token sequence matching.
    * **LangGraph Agent Workflow**: Constructed state machine loops (state.py, tools.py, and nodes.py) around the local Prash model.
    * **Advanced Controls**: Implemented absolute volume setting (0-100%) and individual application window minimization (`minimize_window` tool) in `automation.py`.
12. **Performance & Hybrid Observability (`redis_cache.py`, `gpu_scheduler.py`, `observability.py`)**:
    * **Dual-Layer Caching**: In-memory dict + Redis hybrid cache engine with hit ratio tracking and TTL eviction for LLM prompts and RAG queries.
    * **GPU VRAM Scheduler**: CUDA VRAM allocation tracking, lazy model loading on demand, and idle LRU model offloading.
    * **Telemetry Tracing**: Distributed trace correlation IDs (`trace_id`), crash reporting, and system hardware health monitoring.
13. **Cross-Platform Compatibility & Mobile Sync (`cross_platform.py`)**:
    * **OS Abstraction Layer**: Standardized platform detection and execution matrix supporting Windows, Linux, and macOS.
    * **Mobile Companion Sync Broker**: Encrypted local socket pairing for Android and iOS companion apps with clipboard and memory state synchronization (`data/paired_devices.json`).
14. **System Benchmarks & Local Backups (`test_runner.py`)**:
    * **Performance Benchmarks Runner**: Automated benchmark execution measuring CPU compute speed, memory throughput, and LLM latency.
    * **Local Backup & Restore Manager**: Compressed ZIP backup creation and data restoration manager (`data/backups/`).
15. **Autonomous Intelligence Engine (`autonomous_engine.py`)**:
    * **Workflow & Habit Learning**: User daily routine pattern recognition and macro automation suggestions (`data/user_habits.json`).
    * **Predictive Execution**: Time-of-day predictive task scheduler.
    * **Personal AI Project Manager**: Long-term goal milestone tracking (`data/long_term_goals.json`) and self-improving prompt optimizer.

---

## ⚙️ Technical Stack Core Imports & Purposes

The backend utilizes specific libraries to construct the Next-Generation AI OS capabilities:

| Import / Package | Domain Location | Purpose & Capability |
|---|---|---|
| **`fastapi` / `uvicorn`** | `backend/main.py`, `backend/api/` | Hosts the server and handles REST routes, middleware, and duplex websocket streams. |
| **`pydantic` / `pydantic_settings`** | `backend/config.py`, `backend/models/` | Centralized settings management (hot-reloads via `.env`) and strict JSON schemas. |
| **`loguru`** | `backend/utils/logger.py` | Unified logger with rotating log files, log levels, and EventBus stream hookups. |
| **`networkx`** | `backend/services/hybrid_memory_system.py` | Constructs and queries entity relationship nodes and edges for the Knowledge Graph. |
| **`cryptography` / `keyring`** | `backend/services/security/vault.py` | Encrypted credential vault with fallback AES symmetric ciphers and Windows Locker. |
| **`pypdf`** | `backend/services/rag_service.py` | Parses and extracts structured page texts from local PDF documents recursively. |
| **`zipfile` / `xml.etree.ElementTree`** | `backend/services/rag_service.py` | Natively extracts paragraph and slide texts from DOCX / PPTX OpenXML archives. |
| **`chromadb`** | `backend/services/memory.py`, `rag_service.py` | Local vector database indexing and SentenceTransformers semantic search matching. |
| **`sqlalchemy` / `sqlite3`** | `backend/models/database.py` | Persistent SQLite structured storage for chat message histories, preferences, and logs. |
| **`asyncio`** | `backend/utils/`, `backend/mcp/` | Asynchronous task queues, event buses, and non-blocking MCP server subprocesses. |
| **`win32gui` / `win32process` / `pywinauto`** | `backend/services/skills/` | Low-level OS active window tracking, min/max controls, and volume mixer interactions. |
| **`playwright`** | `backend/services/browser.py` | Automated headless/headed browser sessions and fast DuckDuckGo web searching. |

---

## ⚠️ Limitations & Bugs

* **OS Platform Locks:** Desktop control hooks (`win32gui`, `pywinauto`) lock the application solely to **Windows OS**. It will not run on macOS or Linux without extensive service refactoring.
* **Headless Browser Bans:** Headless browser crawls (Playwright) are frequently flagged by Cloudflare or CAPTCHA blockers, requiring a manual headed browser run or fallback search.
* **Clap Calibration Spike:** The adaptive noise floor calculation requires a 2-second calibration period on launch; triggers during this window are ignored.
* **Tesseract Executable Path:** OCR features fail if the Tesseract-OCR binary is not pre-installed or its folder is missing from the environment PATH.

---

## 🎯 Capability Roadmap

The roadmap includes the following planned system capabilities and enhancements:

1. **Security Sandbox & Vault**: Implement local credential locking and isolate script execution inside Docker/Windows Sandbox environments.
2. **MCP Client & Server Transition**: Standardize all desktop skills under the Model Context Protocol (FastMCP) and remove the hardcoded tool definition schemas.
3. **Personal Knowledge Hub (RAG)**: Index local documents (PDF, DOCX, Obsidian vault) with semantic RAG search to serve as the unified agent knowledge repository.
4. **Developer/Coding Agent**: Design a sandbox coding assistant to automate bug localization and unit test generation.
