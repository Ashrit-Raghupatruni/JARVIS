# 🤖 JARVIS — AI Desktop Assistant

<div align="center">

**A production-grade, voice-controlled AI desktop assistant for Windows**

*Inspired by Iron Man's JARVIS*

![Version](https://img.shields.io/badge/version-1.0.0-cyan)
![Platform](https://img.shields.io/badge/platform-Windows-blue)
![License](https://img.shields.io/badge/license-MIT-green)

</div>

---

## ✨ Features

### 🎤 Voice Control
- **Wake Word Activation** — Say "Hey Jarvis" to activate
- **Natural Speech Recognition** — Powered by faster-whisper
- **Natural Speech Synthesis** — Responds with a refined male voice via edge-tts (configured to exclude female voices)
- **Push-to-Talk** — Press `Ctrl+Space` as a fallback

### 🎨 Visual HUD Interface
- **3D WebGL Arc Reactor** — Procedural, fully transparent 3D wireframe Arc Reactor (notched concentric rings, gear ticks, ticking LEDs, and radial copper coils) rotating in opposite directions and pulsing in real-time matching the voice volume amplitude.
- **Holographic HUD Overlay** — Clean, integrated central "J.A.R.V.I.S." title and active state indicator ("SYSTEM READY", "LISTENING", "THINKING") directly inside the core of the Arc Reactor.
- **Context-Aware Siri Widget** — A floating Siri-like voice wave widget that automatically appears at the top center of your screen when calling JARVIS from background applications (using `Ctrl+Space`, claps, or voice wake words) and automatically hides when you focus on the main app.
- **Webcam Hand Gestures** — Control the 3D viewport rotation and zoom levels in real-time using local MediaPipe hand landmark skeleton tracking over your webcam feed.

### 🧠 AI Brain & Orchestration
- **Intelligent LLM Router** — Auto-measures response times, first-token latency, completion speed, success rate, cost, and quality to rank and select providers (Ollama, Gemini, Groq, OpenAI, OpenRouter) dynamically
- **Self-Improving Brain** — Extracts corrections and preferences dynamically from chat logs to adapt to the user's workflow
- **Resilient Tool calling & Fallbacks** — Try-catch wrappers fallback to tool-less completions on schema errors or formatting issues, with direct async awaiting for automation tools
- **Gemini Pydantic Integration** — Conversational history utilizes native `google-genai` Content SDK classes for clean type validation
- **Double-Clap Welcome Flow** — Managed background listener (`ClapService`) that triggers a customized welcome actions sequence (Spotify song, side-by-side Chrome panels, ElevenLabs TTS welcome greeting, and Cursor activation) on double claps
- **Drag-and-Drop File Upload** — Drag and drop text, source code, logs, and markdown files directly into the frontend chat panel to easily analyze them
- **Multi-turn Context** — Remembers conversation history
- **Tool Calling** — Executes real actions on your computer
- **Agent Architecture** — Planner → Automation/Browser/Screen/Memory agents
- **Multimodal Vision** — Screen analysis via Gemini/OpenAI Vision (cloud)
- **High-Performance Voice Concurrency** — WebSocket background task queue (`voice_queue`) sequentially processes audio chunks/PTT toggles, allowing instant interrupt processing and session isolation to discard stale TTS outputs

### 🖥️ Computer Control
- Open & close applications
- Type text & use keyboard shortcuts
- Control mouse movement and clicks
- Create, rename, and organize files
- Run terminal commands (with safety checks)
- Minimize/maximize windows

### 👁️ Screen Understanding
- Capture and analyze screenshots
- Read on-screen text with OCR
- Answer questions about visible content
- Detect active window and monitor info

### 🌐 Browser Automation
- Open websites and search the web
- Fill forms and click elements
- Navigate tabs and pages
- Extract web page content

### 📰 News, Digest & Deep Research (Ported from Friday/OpenJarvis)
- **World & Finance RSS Aggregator** — Fetches and formats real-time headlines from BBC, CNBC, Bloomberg, NYTimes, AlJazeera, Reuters, and MarketWatch in parallel.
- **World Monitor Dashboards** — Launches live visual maps and market monitors (`worldmonitor.app` & `finance.worldmonitor.app`) in your browser.
- **Daily Morning Digest** — Generates daily briefings compiling weather, upcoming calendar events, CPU/RAM metrics, and world headlines.
- **Multi-Step Deep Research** — Executes deep web research queries, scraper engines, and compiles citation-heavy synthesized summaries.

### 💾 Memory System
- Remembers your name, preferences, and habits
- Semantic search across past conversations
- Persistent storage with ChromaDB + SQLite
- Context-aware responses

### 🛡️ Safety System
- Confirms before deleting files, shutdown, or risky commands
- Blocks malicious requests
- Sandboxed terminal execution
- Command sanitization

---

## 🚀 Quick Start

### Prerequisites

- **Windows 10/11**
- **Python 3.11+** — [Download](https://python.org)
- **Node.js 20+** — [Download](https://nodejs.org)
- **Git** — [Download](https://git-scm.com)
- **Ollama** — [Download](https://ollama.com/) (Primary AI Brain — runs locally, free)
- **Google Gemini API Key** — [Get one](https://aistudio.google.com/) (Optional, for cloud fallback & vision)
- **OpenAI API Key** — [Get one](https://platform.openai.com/api-keys) (Optional, for additional fallback)
- **Tesseract OCR** (optional, for screen reading) — [Download](https://github.com/UB-Mannheim/tesseract/wiki)

### Installation

#### Option 1: One-Click Setup (Recommended)

```bash
# Clone the repository
git clone https://github.com/your-username/JARVIS.git
cd JARVIS

# Run the setup script (will offer to launch JARVIS after setup)
setup.bat
```

#### Option 2: Manual Setup

```bash
# 1. Clone the repository
git clone https://github.com/your-username/JARVIS.git
cd JARVIS

# 2. Set up the backend
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# 3. Set up the frontend
cd ..\frontend
npm install

# 4. Pull the Ollama model
ollama pull qwen2.5-coder:3b

# 5. Configure environment
cd ..
copy .env.example .env
# Edit .env — defaults to Ollama (no API keys needed for basic use)

# 6. Launch JARVIS
.\start.bat
```

### Running JARVIS

#### Option A: Run `start.bat` (Recommended)
- **File Explorer**: Double-click `start.bat` in the project root.
- **PowerShell / CMD**: Type `.\start.bat` and press Enter. 

> ⚠️ **Important:** Do NOT run `python start.bat` or `python setup.bat`. Batch files (`.bat`) are Windows Command Prompt scripts, and running them with python will result in a python syntax error.

#### Option B: From PowerShell
```powershell
cd frontend
npm run dev
```

> ⚠️ **VS Code Terminal Users:** If you get `TypeError: Cannot read properties of undefined (reading 'requestSingleInstanceLock')`, this is because VS Code sets `ELECTRON_RUN_AS_NODE=1` in its terminal. Fix it by running:
> ```powershell
> $env:ELECTRON_RUN_AS_NODE=""; npm run dev
> ```
> Or simply use `.\start.bat` which handles this automatically.

### Configuration

Copy `.env.example` to `.env` and configure:

```env
# Primary LLM Provider Configuration
LLM_PROVIDER=ollama           # Options: ollama, gemini, openai

# Ollama Settings (Primary — Local, Free)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5-coder:3b

# Google Gemini API Settings (Cloud Fallback + Vision)
GEMINI_API_KEY=AIzaSy...your-gemini-key-here
GEMINI_MODEL=gemini-2.0-flash

# Groq API Settings (High-Speed Cloud Fallback)
GROQ_API_KEY=gsk_your-groq-key-here
GROQ_MODEL=llama-3.3-70b-versatile

# OpenRouter API Settings (Cloud Fallback)
OPENROUTER_API_KEY=sk-or-v1-your-openrouter-key-here
OPENROUTER_MODEL=meta-llama/llama-3.3-70b-instruct:free

# OpenAI API Settings (Cloud Fallback/Optional)
OPENAI_API_KEY=sk-your-openai-key-here
OPENAI_MODEL=gpt-4o

# Optional Voice Settings
WHISPER_MODEL=small           # Speech recognition model
TTS_VOICE=en-US-GuyNeural     # Text-to-speech voice
WAKE_WORD_THRESHOLD=0.5       # Wake word sensitivity
```

### 🧠 Ollama + Multi-Cloud Failover Setup

JARVIS uses a production-grade, highly resilient multi-provider AI system designed to ensure 100% availability:

1. **Primary AI Brain (Ollama — Local)**
   - **Performance**: Fast local inference with zero API costs and complete privacy.
   - **Model**: `qwen2.5-coder:3b` — a capable coding/assistant model that runs on standard hardware.
   - **Setup**: Install [Ollama](https://ollama.com/), then run `ollama pull qwen2.5-coder:3b`.
   - **No API key required** — everything runs locally on your machine.

2. **Autonomous Cloud Failover Chain**
    - If the active provider is offline, runs out of credits, errors out, or fails to respond within **30 seconds**, JARVIS automatically switches to the next provider in the chain:
      * **Ollama API** (Local Primary)
      * **Google Gemini API** (`gemini-2.0-flash`)
      * **Groq API** (`llama-3.3-70b-versatile`)
      * **OpenAI API** (`gpt-4o`)
      * **OpenRouter API** (`meta-llama/llama-3.3-70b-instruct:free`)
   - Failovers are handled in real-time on a per-request basis to prevent user-facing downtime.

3. **Multimodal Screen Vision**
   - Screen analysis requests ("what's on my screen?") require vision capabilities and route to **Gemini Vision** as primary, with **OpenAI GPT-4o Vision** as backup.
   - Vision requests run over the cloud since the local model runs on text-only architectures.

---


## 🎮 Usage

### Voice Commands

| Say this... | JARVIS does... |
|-------------|---------------|
| "Hey Jarvis" | Activates and listens |
| "Open Chrome" | Launches Google Chrome |
| "Create a folder called AI Projects" | Creates the folder |
| "What's on my screen?" | Analyzes visible content |
| "Search for AI internships" | Opens browser and searches |
| "Type this email: Dear sir..." | Types the text |
| "Minimize all windows" | Minimizes everything |
| "Remember my name is Ashri" | Stores in memory |
| "What's my name?" | Retrieves from memory |

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+Space` | Push-to-talk (hold to speak) |
| `Ctrl+Shift+J` | Toggle JARVIS window |
| `Escape` | Close settings/panels |

---

## 🏗️ Architecture

```
JARVIS/
├── frontend/          # Electron + React + Tailwind
│   ├── src/
│   │   ├── main/      # Electron main process
│   │   ├── preload/   # IPC bridge
│   │   └── renderer/  # React app
│   └── package.json
│
├── backend/           # Python + FastAPI
│   ├── api/           # WebSocket & REST endpoints
│   ├── agents/        # AI agent system
│   ├── services/      # Core services (STT, TTS, LLM, etc.)
│   ├── models/        # Data models
│   └── main.py        # Entry point
│
├── .env.example       # Configuration template
├── start.bat          # Launch script
└── setup.bat          # Installation script
```

### Communication Flow

```
User speaks → Mic capture → WebSocket → Wake Word Detection
→ Speech-to-Text (Whisper) → LLM (Ollama Local → Gemini → OpenAI Fallback) → Tool Execution
→ Response → Text-to-Speech (edge-tts) → WebSocket → Speaker
```

---

## 🔧 Development

### Running in Development Mode

The Electron frontend automatically manages the backend server. You only need one command:

```powershell
# From the project root
start.bat

# Or from the frontend directory
cd frontend
npm run dev
```

> **Note:** The Electron main process spawns the Python backend automatically.
> You do NOT need to start the backend separately.

> ⚠️ **Important:** Always run from **PowerShell** or use `start.bat`.
> VS Code's integrated terminal sets `ELECTRON_RUN_AS_NODE=1` which prevents
> Electron from loading correctly. The npm scripts clear this automatically,
> but if you encounter issues, run: `$env:ELECTRON_RUN_AS_NODE=""` first.

### Running Automated Tests

To verify that all REST endpoints are working correctly, run the automated route test suite:

```bash
cd frontend
npm test
```

This spins up the FastAPI backend, tests all 7 REST routes (including health checks, system status, voices list, monitor detection, history, settings management, and commands), and automatically shuts down the server.

### Building for Production

```bash
cd frontend
npm run build
```

---

## 📋 Tech Stack

| Component | Technology |
|-----------|-----------|
| Frontend | Electron + React 19 + Tailwind CSS 4 |
| Backend | Python + FastAPI |
| AI Brain | Ollama qwen2.5-coder:3b (Local Primary) + Gemini (Fallback) + OpenAI GPT-4o (Fallback) |
| Speech-to-Text | faster-whisper |
| Text-to-Speech | edge-tts |
| Wake Word | openwakeword |
| Desktop Automation | pywinauto + PyAutoGUI |
| Browser Automation | Playwright |
| OCR | pytesseract |
| Memory | ChromaDB + SQLite |
| Communication | WebSocket |

---

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License.

---

<div align="center">

**Built with ❤️ and AI**

*"At your service, sir."*

</div>
