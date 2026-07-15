# 🛠️ Technical Specification — JARVIS Architecture & Technologies

## 1. System Overview

JARVIS is built as a split-architecture desktop application:
1. **Frontend (Presentation Layer)**: An Electron-based shell wrapping a React 19 application. It handles user inputs (keyboard, mouse, mic), displays real-time agent plans, transcripts, and status animations (Orb, VoiceWave).
2. **Backend (Application Layer)**: A Python FastAPI application that handles speech services (STT, TTS), audio queue management, LLM provider routing, planning, subagent orchestration, and hardware controls.
3. **Communication**: Real-time communication occurs over a local **WebSocket connection** (`/api/voice`) for duplex audio streaming and state synchronization, alongside standard **REST endpoints** for settings and history.

```mermaid
graph TD
    User([User]) <-->|Voice/UI| Frontend[Electron + React UI]
    Frontend <-->|WebSocket & REST| Backend[FastAPI Server]
    
    subgraph Backend Services
        Router[LLM Router]
        Planner[Agent Planner]
        MemoryService[Memory & Embeddings]
        STT[Whisper Speech-to-Text]
        TTS[Edge-TTS Text-to-Speech]
        Wake[OpenWakeWord Engine]
        Clap[Clap Listener]
        Auto[PyAutoGUI/pywinauto OS Control]
        Browser[Playwright Browser Automation]
    end
    
    Backend <--> Router
    Backend <--> STT
    Backend <--> TTS
    Backend <--> Wake
    Backend <--> Clap
    Backend <--> Auto
    Backend <--> Browser
    Backend <--> MemoryService
    
    subgraph Databases
        SQLite[(SQLite DB via aiosqlite)]
        Chroma[(ChromaDB Vector DB)]
    end
    
    MemoryService <--> SQLite
    MemoryService <--> Chroma
    Backend <--> SQLite
    
    subgraph LLM Providers
        Ollama[Ollama - Local primary]
        Gemini[Gemini API - Cloud]
        Groq[Groq API - Cloud]
        OpenAI[OpenAI - Cloud]
        OpenRouter[OpenRouter - Cloud]
    end
    
    Router <--> Ollama
    Router <--> Gemini
    Router <--> Groq
    Router <--> OpenAI
    Router <--> OpenRouter
```

---

## 2. Technology Stack

| Layer | Component | Selected Technology | Rationale |
| :--- | :--- | :--- | :--- |
| **Frontend** | Shell Framework | Electron | Native Windows window creation, desktop shortcuts, IPC bindings, background window execution. |
| | Render Framework | React 19 | Highly reactive state binding, component lifecycle management. |
| | CSS Framework | Tailwind CSS 4 | Custom utility-first classes, modern variables, and fast compilation. |
| | State Management | Zustand | Lightweight, hooks-based global state container for audio streams and app states. |
| | 3D Graphics | Three.js | Real-time WebGL rendering engine for the cognitive 3D Orb visualizations and drift particles. |
| | Gesture Tracking | MediaPipe Tasks-Vision | Local machine learning hand landmark tracking for viewport rotation and zoom triggers. |
| **Backend** | API Engine | FastAPI + Uvicorn | High-performance asynchronous REST and WebSockets. |
| | Speech-to-Text | faster-whisper | Fast, local transformer model inference for audio transcription. |
| | Text-to-Speech | edge-tts | Free, extremely natural speech synthesis utilizing Microsoft Edge's translation services. |
| | Wake Word | openwakeword | Highly customizable local wake word engine with minimal CPU overhead. |
| | Sound Activator | PyAudio | Raw audio input analysis for clap pattern recognition (peaks and intervals). |
| | OS Automation | pywinauto + PyAutoGUI | Complete desktop orchestration, window focusing, mouse clicking, and keyboard shortcuts. |
| | Web Automation | Playwright (Python) | Robust, sandboxed chromium automation, scraping, and deep research actions. |
| | OCR Engine | Pytesseract | Local image-to-text decoding fallback. |
| **Database** | Relational Store | SQLAlchemy + aiosqlite | Asynchronous ORM and non-blocking SQLite database driver. |
| | Vector Database | ChromaDB | Local, lightweight vector storage for long-term semantic memories. |
| **Orchestrator**| Local LLM | Ollama (`qwen2.5-coder:3b`) | Free, offline, high-speed coding and tool-calling model. |
| | Cloud LLM Router| Google GenAI SDK, OpenAI, Groq | Multi-provider failover chains with automatic performance benchmarking. |

---

## 3. Authentication & Security (Local-First Design)

* **No Multi-Tenant Authentication**:
  * Since JARVIS runs locally as a Windows desktop application, there is no web auth (OAuth/JWT/Sessions) needed.
  * System security is tied directly to the Windows User Profile context.
* **Credential Storage**:
  * API Keys (Gemini, Groq, OpenAI, OpenRouter) are loaded strictly from a local `.env` file in the root directory.
  * The frontend accesses keys via secure Electron IPC channels; they are never exposed to external web environments.
* **Safety Sandbox**:
  * The `SafetyService` checks all incoming text prompts and planned CLI commands against a banned keywords dictionary.
  * System critical commands (e.g., system shutdown, deleting directories, file system overrides) prompt the user with a confirmation modal before execution.
* **Camera Access Privacy**:
  * The webcam feed used for hand tracking is processed strictly inside the local renderer process (browser sandbox).
  * Video streams, images, and landmark coordinates are handled entirely in transient memory and immediately discarded. No video data is ever saved to the local file system or uploaded to external cloud endpoints.

---

## 4. Database Setup & Configurations

The SQLite database (`data/jarvis.db`) is managed asynchronously:
* **Engine**: Async SQLAlchemy engine: `sqlite+aiosqlite:///data/jarvis.db`.
* **Pooling**: Concurrency pre-ping to ensure active connection validation: `pool_pre_ping=True`.
* **Lifecycle**: Initialized on FastAPI startup (`init_db`) and gracefully disposed on shutdown (`close_db`).
* **Semantic Storage**: ChromaDB is stored under `data/chroma`. Semantic memory chunks are embedded and queried locally using basic sentence-transformers or cloud-based embedding fallbacks.

---

## 5. API Endpoints

### 5.1. WebSocket Endpoints
* **`WS /api/voice`**: Main communication channel.
  * **Client ➔ Server**: Sends raw audio chunks, Push-To-Talk events, or text commands.
  * **Server ➔ Client**: Sends assistant states, STT transcripts, thinking states, agent progress logs, and TTS audio chunks (MP3).

### 5.2. REST Endpoints
* **`GET /api/health`**: Simple health check.
* **`GET /api/status`**: Detailed system health monitor (states of speech pipelines, memory, and CPU/RAM metrics).
* **`GET /api/voices`**: Lists all available Edge-TTS voices configured in the system.
* **`GET /api/monitors`**: Detects connected physical displays, dimensions, and layout offsets.
* **`GET /api/history`**: Retrieves past conversation logs grouped by `conversation_id`.
* **`POST /api/settings`**: Updates and persists user preferences in the SQLite `user_preferences` table.
* **`POST /api/command`**: Runs a direct terminal command (after safety checks and validation).
