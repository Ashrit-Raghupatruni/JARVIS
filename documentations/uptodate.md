# JARVIS — Comprehensive Status, Tech Stack, & Features Overview

This document serves as the single source of truth for JARVIS's current capabilities, system architecture, tech stack, and development status. **Last Updated:** July 22, 2026

---

## 📋 Tech Stack

The architecture is split into a **React + Electron** desktop client (frontend) and a **FastAPI + WebSockets** backend service (Python).

### Frontend (Desktop Client)
* **Shell/Container:** Electron v35.0.0 (manages OS-level desktop windows, system tray, global shortcut registration)
* **Framework:** React v19.1.0 + TypeScript v5.8.0 + Vite v6.4.2
* **Build System:** `electron-vite` v3.1.0 + `electron-builder` v25.1.0
* **Styling:** Tailwind CSS v4.1.0 + `@tailwindcss/vite`
* **State Management:** Zustand v5.0.0
* **3D Visuals:** Three.js v0.185.1 (WebGL rendering of a procedural 3D Arc Reactor focal core with particle fields and chromatic aberration shader passes)
* **Visual Workflow Studio:** React SVG canvas with interactive Bezier connectors, node library, parameter tuning, and workflow templates (`VisualWorkflowBuilder.tsx`)
* **Task Queue Manager:** Drag-and-drop task queue visualizer (`TaskQueueManager.tsx`)
* **Live Execution Timeline:** 9-stage visual execution pipeline component (`TaskProgress.tsx`)
* **Communication:** Native WebSockets for real-time bidirectional status, audio stream, and command events

### Backend (Python Service)
* **Core Web Server:** FastAPI v0.115.9 + Uvicorn v0.34.2 (runs locally on port 8000)
* **Database (Relational):** SQLite + SQLAlchemy ORM v2.0.41 + `aiosqlite` v0.21.0 (non-blocking async transactions)
* **Database (Vector):** ChromaDB v1.0.7 (vector storage for semantic long-term memory & RAG Knowledge Hub)
* **Task Queue Service:** `TaskQueueService` (`backend/services/task_queue.py`) managing thread-safe task priorities, pause/resume, cancellations, and persistent JSON storage.
* **Embeddings Model:** `sentence-transformers` v4.1.0 (runs `all-MiniLM-L6-v2` locally for context matching)
* **Utilities:** `loguru` v0.7.3 (structured logging), `python-dotenv` v1.1.0 (config management)

### AI Models & Integrations
* **Prash Local AI Engine:** Custom 0.70M-parameter Transformer model trained on synthetic command datasets.
  * **Dynamic Handoff:** Computes prediction entropy; if non-confident, seamlessly cascades to cloud providers with zero visible errors.
* **LLM Engine & Intelligent Router:** Multi-provider orchestration client supporting Ollama, Google Gemini, Groq, OpenAI, and OpenRouter:
  * **Dynamic Ranking Router:** Measures latency, throughput, cost, and quality with circuit-breakers (5-minute cooldown).
  * **Response Quality Evaluator & Web Recovery:** If LLM output fails or returns empty payloads, automatically runs autonomous web research.
* **Speech-to-Text (STT):** Local `faster-whisper` v1.1.1 (pre-loaded in background for instant offline fallback).
* **Text-to-Speech (TTS):** Microsoft `edge-tts` v7.2.8 (`en-GB-RyanNeural`, `en-US-GuyNeural`) + ElevenLabs API.
* **Wake Word:** `openwakeword` v0.6.0 (running ONNX runtime for local "Hey Jarvis" keyword trigger with 0.35 confidence threshold).
* **Clap Listener:** `sounddevice` clap listener with active voice state guard (ignores mic spikes during TTS speech or processing).

---

## 🛠️ Architecture & Major Modules

```
                             ┌──────────────────────────────────┐
                             │        ELECTRON FRONTEND         │
                             │   (React 19, Visual Workflow,    │
                             │    Task Queue, Live Timeline)    │
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
│   VOICE AGENT     │       │   PLANNER AGENT   │       │ TASK QUEUE SERVICE│      │   CLAP LISTENER   │
│ - Wake Word       │       │ - Direct Tools    │       │ - Priority Queue  │      │ - Active Guard    │
│ - Instant Whisper │       │ - Skill Registry  │       │ - Task Persistence│      │ - Threshold 0.045 │
└───────────────────┘       └───────────────────┘       └───────────────────┘      └───────────────────┘
```

---

## 🎯 Verification & Build Confirmation

- **Backend Python Compilation**: `python -m py_compile backend/agents/planner.py backend/services/llm.py backend/main.py backend/services/task_queue.py` → **`0 errors`**.
- **Frontend Production Build**: `npm --prefix frontend run build` → **`0 errors`** (`built in 7.19s`).
