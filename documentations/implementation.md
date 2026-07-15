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
│   │   ├── planner.py       # Reasoning agent that generates multi-step plans
│   │   ├── subagent.py      # Base class for specialized worker agents
│   │   └── voice.py         # Handles voice stream loop processing
│   ├── models/
│   │   ├── database.py      # Async SQLAlchemy SQLite model classes
│   │   └── schemas.py       # Pydantic validation models
│   ├── services/
│   │   ├── automation.py    # pywinauto and PyAutoGUI GUI automation
│   │   ├── browser.py       # Playwright browser manager
│   │   ├── clap.py          # Background microphone clap listener
│   │   ├── llm.py           # Model bindings wrapper for APIs & local Ollama
│   │   ├── llm_router.py    # Metric analyzer & fallback router
│   │   ├── memory.py        # SQLite + ChromaDB semantic cache
│   │   ├── safety.py        # Banned keyword & command safety checks
│   │   ├── screen.py        # Screenshot capturing & vision API
│   │   ├── stt.py           # faster-whisper local STT engine
│   │   ├── tts.py           # edge-tts voice synthesis engine
│   │   └── wake_word.py     # Local openwakeword wake word pipeline
│   ├── utils/
│   │   └── logger.py        # Loguru console and file logging setup
│   ├── config.py            # Centralized settings loader (Pydantic Settings)
│   └── main.py              # Application server entry point (FastAPI)
│
├── frontend/
│   ├── src/
│   │   ├── main/            # Electron main process (spawns backend, manages window)
│   │   ├── preload/         # IPC bridge script
│   │   └── renderer/        # React 19 visual application
│   │       ├── src/
│   │       │   ├── components/  # Orb, ChatPanel, VoiceWave, Settings, TitleBar
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
                   │        ├──► Initialize DB schemas (SQLite / aiosqlite)
                   │        ├──► Initialize ChromaDB vector workspace
                   │        ├──► Spin up ClapService background thread
                   │        └──► Expose REST & WebSockets server on port 8000
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
* **Usage**: Focuses specific window titles (e.g. Chrome, Spotify), types text templates, and inputs system-level hotkeys (e.g. `Ctrl+Alt+Tab`).

### 4.2. Browser Service (`backend/services/browser.py`)
* **Library**: `Playwright` (Chromium engine).
* **Usage**: Headless navigation, scrolling, reading selectors, clicking buttons, submitting text input forms, and scraping articles.

### 4.3. Screen Service (`backend/services/screen.py`)
* **Libraries**: `pyautogui.screenshot()` for capturing displays. `pytesseract` for local OCR translation.
* **Usage**: Captures screen images, encodes them to base64, and dispatches them to multimodal models (`Gemini-2.0-Flash` / `GPT-4o`) to answer queries about active developer workflows or errors.
