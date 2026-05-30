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
- **Natural Speech Synthesis** — Responds with a refined voice via edge-tts
- **Push-to-Talk** — Press `Ctrl+Space` as a fallback

### 🧠 AI Brain
- **Google Gemini 1.5 Flash Powered** — Primary LLM providing extremely fast and intelligent context-aware reasoning
- **Seamless Failover** — Automatically switches to OpenAI GPT-4o if Gemini is offline, rate-limited, or not configured
- **Multi-turn Context** — Remembers conversation history
- **Tool Calling** — Executes real actions on your computer
- **Agent Architecture** — Planner → Automation/Browser/Screen/Memory agents

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
- **Google Gemini API Key** — [Get one](https://aistudio.google.com/) (Primary AI Brain)
- **OpenAI API Key** — [Get one](https://platform.openai.com/api-keys) (Optional, for automatic failover/fallback)
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

# 4. Configure environment
cd ..
copy .env.example .env
# Edit .env and add your GEMINI_API_KEY (and optionally OPENAI_API_KEY)

# 5. Launch JARVIS
start.bat
```

### Running JARVIS

#### Option A: Double-click `start.bat` (Recommended)
The simplest way — just double-click `start.bat` in the project root.

#### Option B: From PowerShell
```powershell
cd frontend
npm run dev
```

> ⚠️ **VS Code Terminal Users:** If you get `TypeError: Cannot read properties of undefined (reading 'requestSingleInstanceLock')`, this is because VS Code sets `ELECTRON_RUN_AS_NODE=1` in its terminal. Fix it by running:
> ```powershell
> $env:ELECTRON_RUN_AS_NODE=""; npm run dev
> ```
> Or simply use `start.bat` which handles this automatically.

### Configuration

Copy `.env.example` to `.env` and configure:

```env
# Primary LLM Provider Configuration
LLM_PROVIDER=gemini           # Options: gemini, openai

# Google Gemini API Settings (Primary)
GEMINI_API_KEY=AIzaSy...your-gemini-key-here
GEMINI_MODEL=gemini-1.5-flash

# OpenAI API Settings (Fallback/Optional)
OPENAI_API_KEY=sk-your-openai-key-here
OPENAI_MODEL=gpt-4o

# Optional Voice Settings
WHISPER_MODEL=small           # Speech recognition model
TTS_VOICE=en-US-GuyNeural     # Text-to-speech voice
WAKE_WORD_THRESHOLD=0.5       # Wake word sensitivity
```

### 🧠 Gemini 1.5 Flash & Failover Setup

JARVIS uses a production-grade dual-engine AI system designed to ensure 100% uptime and low-latency responses:

1. **Primary AI Brain (Google Gemini 1.5 Flash)**
   - **Performance**: Near-instant speech-to-text-to-speech loops (~1.5s latency).
   - **API Key**: Obtain a free API key from [Google AI Studio](https://aistudio.google.com/).
   - **Native Multimodality**: Allows JARVIS to natively analyze your screen screenshots with Gemini's vision capability.

2. **Automatic Failover Brain (OpenAI GPT-4o)**
   - **Robustness**: If Gemini's API key is not supplied, or if the Gemini service encounters rate limits, quota limits, or server downtime, the core system **automatically and transparently fails over to OpenAI**.
   - **API Key**: Add your `OPENAI_API_KEY` under the OpenAI API settings in the `.env` file to enable this safety backup.

3. **Multimodal Screen Vision Fallback**
   - Screen analysis requests (`"what's on my screen?"`) will use Gemini Vision as primary. If it encounters a connection issue or is unconfigured, it seamlessly utilizes OpenAI GPT-4o Vision to provide the answer without interrupting the user.

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
→ Speech-to-Text (Whisper) → LLM (Gemini 1.5 Flash w/ OpenAI Fallback) → Tool Execution
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
| AI Brain | Google Gemini 1.5 Flash (Primary) + OpenAI GPT-4o (Fallback) |
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
