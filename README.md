# 🤖 JARVIS — AI Desktop Assistant

<div align="center">

**A voice-controlled AI desktop assistant for Windows**

*Inspired by Iron Man's JARVIS*

![Version](https://img.shields.io/badge/version-1.0.0-cyan)
![Platform](https://img.shields.io/badge/platform-Windows-blue)
![License](https://img.shields.io/badge/license-MIT-green)

</div>

---

## ✨ Features

### 🎤 Voice Control, Mobile Companion & Live Mode AI Co-Pilot
- **3-Tier Neural & Offline TTS Pipeline** — Multi-tier voice architecture featuring Microsoft Edge-TTS streaming neural audio with seamless automatic fallback to offline local Piper ONNX neural synthesis and tertiary Windows Native SAPI `SpVoice` / `SpFileStream`. Preserves real-time barge-in and cancellation.
- **Dedicated Live Mode (AI Screen Assistant)** — Real-time continuous desktop observation operating mode. Differential Win32 UIA Scene Graph caching, adaptive backoff observation loop (0.5s active to 2.5s static), next logical guidance, and multi-monitor workspace layout restorer.
- **Persistent Chat History (Claude/GPT-Style)** — Browsable, persistent conversation sessions stored in SQLite (`jarvis.db`) with automatic first-message title generation, session sidebar (`ConversationSidebar.tsx`), inline renaming, deletion, and transcript restoration.
- **Live Mode Browser Automation Engine** — Native multi-step perceive-decide-act-observe agent loop (`run_browser_agent` in `BrowserService`) and `browser_agent_task` tool for autonomous web research.
- **Proactive Desktop Intelligence Suite** — Instant TTS interrupt barge-in (`cancel_playback`), exponential backoff retry decorator, 3.0s vision rate-limiter, Windows Registry boot auto-start (`system_autostart.py`), Clipboard Quick-Action Intelligence (`clipboard_intelligence.py`), session memory continuity (`session_memory.json`), background topic monitoring with content safety filters, and Proactive 2.0 with a 20-minute interjection cooldown timer.
- **Structured Layout & Table OCR Engine** — Bounding box, structured table, and layout extraction in `VisionService` with PP-StructureV3 deep vision, pytesseract, and PIL grid fallback.
- **Fail-Closed Mobile & Telegram Gatekeeper Intercept** — Strictly fail-closed permission gatekeeper. Intercepts laptop window close, terminal exit, or dangerous system commands (`rm -rf`, `shutdown`). Broadcasts high-priority approval cards over WebSocket and Telegram with 1-click `[Approve]` / `[Deny]` control. Fails closed (denies action) if transport is offline.
- **Standalone Backend Hand Tracking CV Worker** — Background `CameraWorker` thread capturing OpenCV frames, classifying landmarks via `GestureEngine` (`PINCH`, `OPEN_PALM`, `FIST`, `SWIPE`), filtering by confidence (`0.7`), and applying `150ms` debouncing. Works even when the Electron window is minimized.
- **Fast Non-Blocking n8n Integration** — Pre-flight TCP socket probing eliminates connection timeout stalls when n8n is offline. Bi-directional Visual Canvas <-> n8n graph translation and 6 LLM tools.
- **Real Mobile Voice Input & Companion App** — Live microphone audio recording streaming base64 chunks over WebSocket to backend `faster-whisper` STT in `mobile_ws.py`. Companion Android app features 8 modular tabs, real-time telemetry HUD streaming, remote screen preview, and dynamic approval cards.
- **Laptop Battery Level Mobile Alerts** — Automatic push & WebSocket notifications sent to phone at 30% (Warning) and 20% (Critical) unplugged battery levels.
- **Double Clap Detection Engine** — Acoustic Peak-to-Average Power Ratio (PAPR > 3.2) transient filter with TTS speaker activity guard; double clapping when JARVIS is minimized or sleeping instantly restores and focuses the desktop window.
- **Wake Word Activation** — Say "Hey Jarvis" to activate (local `openwakeword` engine tuned to 0.35 threshold).

### 🎨 Visual HUD & AI Command Center Studio
- **Unified Command Center** — Modular workspace featuring 3D Orb focal core, AI Chat, Computer Use, Visual Workflow Studio, Task Queue Manager, Telemetry, and RAG Knowledge Hub.
- **Adaptive Responsive Windowing** — Displays full dashboard in fullscreen/maximized mode; auto-hides panels to show ONLY the central 3D Orb HUD when window is unmaximized or resized compact.
- **Battery-Saver WebGL Canvas** — Automatically pauses WebGL rendering loops when window is minimized or hidden.
- **Native Windows UI Automation (UIA)** — `UIAEngine` provides resolution-independent element selection, button clicks by title/name, and focus management.
- **SQLite FTS5 Natural Language File Indexer** — Sub-second natural language file search engine (`FileIndexerService`).
- **Visual Workflow Builder** — Node-based visual workflow editor (`VisualWorkflowBuilder.tsx`) with interactive Bezier SVG connectors, node library, parameter tuning, and reusable workflow templates.
- **Task Queue & Command Scheduler** — Thread-safe task queue visualizer (`TaskQueueManager.tsx`) supporting priority reordering, pause, resume, cancellation, and task persistence.
- **Live Execution Timeline Pipeline** — Visual execution pipeline rendering live status indicators across `Intent Detection` → `Planner` → `Memory` → `Tool Selection` → `RAG` → `Web Research` → `LLM` → `Validation` → `Response`.
- **3D WebGL Arc Reactor Focal Core** — Procedural 3D wireframe centerpiece with 6 animated state transitions (Idle, Listening, Thinking, Speaking, Executing, Error).
- **Command Palette (`Ctrl+K`)** — Instant keyboard shortcut palette for quick actions, system benchmarks, and screen inspection.

### 🧠 AI Brain, Prash Engine & Resilient Fallback Routing (100% Verified)
- **Prash Local AI Engine** — Custom Transformer model evaluating token prediction entropy for instant local responses; seamlessly handoffs to cloud cascade when entropy threshold is exceeded.
- **Multi-Provider Fallback Cascade** — Dynamic routing across Ollama (#1 Local), Gemini, Groq, OpenRouter, and OpenAI with circuit-breaker recovery.
- **Response Quality Evaluator & Web Recovery** — Automatically triggers autonomous web research if LLM outputs fail or return incomplete answers.
- **Instant Factual Fast-Paths** — Deterministic Date/Time, System Control, Volume, and Hardware Telemetry intercepts preventing LLM latency.
- **Interactive Vision & Screen Inspector** — Real-time win32 foreground window HWND inspection and desktop screenshot capture.
- **Playwright Browser Research** — Interactive URL navigation, web search, page summarization, and one-click RAG indexing.
- **RAG Knowledge Hub** — Drag & drop file uploads, folder indexer, live vector search, and document chunk management.
- **4-Tier Memory Explorer** — Working, Long-Term (ChromaDB + NetworkX), Episodic (experiences.db), and Semantic RAG scopes with search, pin, delete, and clear controls.
- **Multi-Agent Orchestrator** — 4 strong domain agents (General, Research, Developer, Automation) with task delegation and IPC state management.
- **Workflow & Macro Manager** — Custom workflow recorder, macro playback, and deletion.


### 🎭 J.A.R.V.I.S. Personality, Learning & Workspace Intelligence
- **J.A.R.V.I.S. Personality Directives** — Refined British butler persona establishing a composed technical co-pilot and partner. Provides polite constructive pushback on unwise or inefficient user decisions, proposes superior technical alternatives, explains reasoning, and maintains dry wit.
- **Workspace Intelligence (`WorkspaceIntelligenceService`)** — Continuously tracks active project context, operational goals, session workflows (`coding`, `research`, `study`), 20-action ring buffer, and long-term user habit transitions persisted in `data/user_habits.json`.
- **Predictive Habit & Action Forecaster** — Uses habit transition matrices to predict your next anticipated desktop action (*"Action A -> Action B"*) and proactively offers macro skill automation when repetitive sequences are detected.
- **Learning & Study Assistant (`LearningSkill`)** — Socratic concept explanations using the Feynman technique (`explain_concept`), interactive quiz generation (`generate_quiz`), and study note summarization (`summarize_study_notes`).
- **Interactive Safety Permission Modal (`SafetyPermissionModal.tsx`)** — Renders backend `permission_request` WebSocket events in the Electron desktop UI with interactive Approve/Deny buttons.
- **"What JARVIS is Seeing" Visualizer (`LivePerceptionVisualizer.tsx`)** — Real-time scene graph panel rendering active window, foreground PID, connected monitors, Win32 UIA control tree, and Workspace Intelligence habit metrics.

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

## 🧩 Registered Skills & Truthful Tool Registry

JARVIS employs a **Truthful Tool Registry** combined with a modular **Skill Plugin Architecture**. Each tool is strictly verified for executable handlers, parameter schemas, and risk tiers.

> **61 Executable Tools** registered in `ToolRegistry` and modular skills

| Category | Primary Tools | Purpose |
|---|---|---|
| 🖥️ **System & Desktop** | `open_application`, `close_application`, `lock_pc`, `get_system_status`, `list_running_processes`, `kill_process`, `get_monitors`, `set_volume` | Windows system controls, process management & hardware telemetry |
| 📁 **Filesystem** | `read_file`, `write_file`, `delete_file`, `create_file`, `copy_file`, `move_file`, `search_files`, `get_file_info` | Safe filesystem operations and file search |
| 🌐 **Web & Browser** | `web_search`, `browser_agent_task`, `play_youtube_video`, `deep_research` | Web searching, Playwright autonomous navigation & research |
| 🪟 **Automation & UI** | `type_text`, `click_element_by_name`, `set_control_value`, `resize_window`, `auto_fill_form`, `execute_rpa_macro` | Desktop RPA, UIA element targeting & form automation |
| 🧠 **Memory & RAG** | `memory_store`, `rag_knowledge_search`, `forget_memory` | 4-tier memory indexing, recall & ChromaDB search |
| 🔌 **Integrations** | `n8n_list_workflows`, `n8n_execute_workflow`, `gmail_list_messages`, `google_calendar_list_events`, `outlook_list_messages` | n8n workflow execution, Google Workspace & Microsoft 365 OAuth |
| 📚 **Learning & Productivity** | `explain_concept`, `generate_quiz`, `take_note`, `list_notes`, `search_notes`, `draft_copy` | Socratic learning, Markdown notes & copy drafting |
| 🧬 **Science & Multimodal** | `balance_chemical_equation`, `calculate_molecular_weight`, `generate_image`, `generate_video`, `generate_3d_asset` | Chemoinformatics, PubChem queries & async media generation |

---

### 📁 FileSkill
**Purpose:** Provides modular tools for natural language file operations and system management.

| Tool | Description |
|------|-------------|
| `smart_file_search` | Fuzzy search for files by name, extension, modified date, and text content |
| `copy_file` | Copy a file from source path to destination path |
| `move_file` | Move a file from source path to destination path |
| `rename_file` | Rename a file at a specific path |
| `safe_delete` | Safely delete a file by moving it to the Recycle Bin |
| `append_to_file` | Append text content to an existing text file |
| `create_file_from_template` | Create a text/markdown file using a pre-defined skeleton template |
| `auto_sort_downloads` | Scan Downloads folder and organize files into categorized subfolders |
| `detect_duplicates` | Check a directory for duplicate files by MD5 hash comparison |

---

### 📬 CommunicationSkill
**Purpose:** Enables JARVIS to interface with email, chat apps, calendars, and mobile devices.

| Tool | Description |
|------|-------------|
| `send_email` | Compose and send an email via SMTP (requires credentials in `.env`) |
| `read_latest_emails` | Fetch recent unread emails from an IMAP inbox |
| `send_whatsapp_message` | Send a WhatsApp message to a phone number via pywhatkit |
| `send_slack_message` | Post a message to a Slack channel via Incoming Webhook |
| `send_discord_message` | Post a message to a Discord channel via Webhook URL |
| `add_calendar_event` | Save a new calendar event/reminder to the local SQLite store |
| `list_calendar_events` | List all upcoming local calendar events and reminders |
| `adb_make_call` | Trigger a phone call on a connected Android device via ADB |
| `adb_send_sms` | Send an SMS from a connected Android device using ADB |

---

### 🖥️ SystemSkill
**Purpose:** Monitor resource utilization, manage Windows startup, control networks, power, and clipboard.

| Tool | Description |
|------|-------------|
| `get_top_processes` | List top running processes sorted by CPU or memory usage |
| `kill_process` | Terminate a running process by PID or name |
| `list_startup_programs` | List all apps registered to run at Windows startup |
| `set_startup_program` | Register or disable an application from Windows startup |
| `get_wifi_status` | Get connected Wi-Fi details and visible nearby SSIDs |
| `set_wifi_power` | Enable or disable the Wi-Fi network interface card |
| `get_battery_status` | Get battery percentage and power source (AC/battery) |
| `set_system_power_action` | Initiate sleep, hibernate, lock, or scheduled shutdown |
| `clipboard_copy` | Write text to the OS clipboard |
| `clipboard_paste` | Read the current text content from the OS clipboard |

---

### 🪟 AppControlSkill
**Purpose:** Automate and control active Windows desktop applications (Office, browsers, VS Code).

| Tool | Description |
|------|-------------|
| `excel_sum_column` | Sum all values in a specific column of the active Excel sheet |
| `excel_write_cell` | Write a value or formula into a cell in the active Excel sheet |
| `word_modify_text` | Append a paragraph to an active Word document (with optional bold) |
| `vscode_open_project` | Launch VS Code and open a specific folder or project directory |
| `vscode_trigger_debug` | Focus VS Code window and trigger the debugger (F5 key) |
| `browser_control_tabs` | Send shortcuts to the browser to manage tabs (open, close, switch) |

---

### 🧠 ContextSkill
**Purpose:** Track active application usage, user focus, and infer work context in real-time.

| Tool | Description |
|------|-------------|
| `get_active_context` | Return the current foreground window, process name, and inferred project category |
| `set_focus_session` | Enable or disable a Do-Not-Disturb deep-focus session |
| `get_focus_status` | Check if a focus session is active and how much time remains |

> **Live Feed:** Context changes are broadcast via WebSocket to the dashboard in real-time (every 30s or on window switch).

---

### 🤖 AgentSkill
**Purpose:** Delegate long-running tasks to autonomous background sub-agents.

| Tool | Description |
|------|-------------|
| `spawn_subagent` | Create and dispatch a background subagent for a multi-step task |
| `get_active_agents` | List all running, completed, or cancelled background agents |
| `abort_subagent` | Cancel the execution of a running agent by its ID |

---

### 📰 NewsSkill
**Purpose:** Fetch real-time world & finance news, open dashboards, and run deep research.

| Tool | Description |
|------|-------------|
| `get_world_news` | Fetch global headlines from BBC, CNBC, NYTimes, AlJazeera in parallel |
| `get_world_finance_news` | Fetch finance headlines from CNBC, Bloomberg, Reuters, MarketWatch |
| `open_world_monitor` | Open `worldmonitor.app` live news dashboard in the browser |
| `open_finance_world_monitor` | Open `finance.worldmonitor.app` market monitor in the browser |
| `morning_digest` | Generate a full morning briefing (weather, news, system stats, calendar) |
| `deep_research` | Run multi-step web research and return a cited summary |

---

### 👁️ VisionSkill
**Purpose:** Inspect and analyze screen UI elements and multi-monitor layouts.

| Tool | Description |
|------|-------------|
| `inspect_accessibility_tree` | Inspect native UI control elements and accessibility tree for a window |
| `get_window_hierarchy` | Enumerate visible top-level windows and child window hierarchies |
| `locate_visual_element` | Ground a target UI element label to screen coordinates `[x, y]` |
| `get_multi_monitor_layout` | Get connected displays, primary monitor, and work-area bounds |

---

### ⚙️ AutomationSkill
**Purpose:** Record and play back keyboard/mouse macros and automate desktop workflows.

| Tool | Description |
|------|-------------|
| `start_workflow_recording` | Start recording user workflow macro steps |
| `stop_workflow_recording` | Stop recording and save the macro to JSON |
| `playback_workflow` | Play back a saved workflow macro |
| `list_workflows` | List all saved workflow macros |
| `arrange_windows_layout` | Tile, split, or snap visible windows into grid layouts |
| `get_clipboard_intelligence` | Read clipboard, auto-detect type (URL/JSON/Code/Path), and view history |
| `check_folder_changes` | Monitor a folder for added, modified, or removed files |

---

### 💻 DeveloperSkill
**Purpose:** Developer assistant for code analysis, git ops, and test generation.

| Tool | Description |
|------|-------------|
| `analyze_repository_structure` | Analyze repo files, languages, framework manifests, LOC, and architecture |
| `localize_bug_from_trace` | Parse error stack traces to pinpoint source files and line numbers |
| `generate_unit_test_stub` | Analyze Python AST to extract functions and generate pytest stubs |
| `generate_pr_description` | Inspect git changes and format a Pull Request title + markdown summary |
| `audit_dependencies` | Audit `requirements.txt` / `package.json` for installed packages |

---

### 🔍 ResearchSkill
**Purpose:** Web research, PDF analysis, fact verification, and browser session management.

| Tool | Description |
|------|-------------|
| `generate_research_report` | Synthesize findings into a structured markdown report with citations |
| `analyze_pdf_document` | Extract text, headings, and structure from a local PDF |
| `verify_fact_claim` | Evaluate a factual claim against reference sources |
| `manage_browser_profile` | Inspect Playwright persistent browser context and saved session states |
| `multi_tab_browser_action` | Simulate multi-tab browser controls (create, list, switch, close tab) |

---

### 🎤 VoiceSkill
**Purpose:** Control speech recognition, TTS, wake-word sensitivity, and speaker identity.

| Tool | Description |
|------|-------------|
| `detect_speaker_emotion` | Classify speaker emotion from audio RMS energy and pitch estimates |
| `manage_speaker_profile` | Retrieve, update, or list speaker profiles and speech preferences |
| `tune_wake_word_threshold` | Tune openwakeword sensitivity (0.1 = sensitive, 0.9 = strict) |
| `get_voice_intelligence_status` | Get full status of STT, TTS, wake-word, and audio stream |

---

### 📋 ProductivitySkill
**Purpose:** Task management, reminders, meeting notes, email drafts, and calendar events.

| Tool | Description |
|------|-------------|
| `get_daily_briefing` | Synthesize an executive morning briefing (date, tasks, reminders, status) |
| `manage_productivity_tasks` | Add, list, complete, or delete TODO tasks |
| `set_reminder` | Set a reminder notification with delay minutes and a message |
| `summarize_meeting_transcript` | Extract summary, key decisions, and action items from a transcript |
| `format_email_draft` | Generate a formatted email subject and body for Gmail or Outlook |
| `manage_calendar_event` | Add or list local calendar events |

---

### 🔌 PluginSkill
**Purpose:** Manage the JARVIS plugin marketplace — install, enable, disable, and run plugins.

| Tool | Description |
|------|-------------|
| `install_plugin` | Install a new plugin into the JARVIS plugin ecosystem |
| `uninstall_plugin` | Uninstall a plugin by name |
| `list_installed_plugins` | List all installed plugins and their status |
| `enable_plugin` | Enable a previously disabled plugin |
| `disable_plugin` | Disable an active plugin without removing it |
| `inspect_plugin_permissions` | Inspect security permissions requested by a plugin |

---

### 🎨 UISkill
**Purpose:** Monitor and control the JARVIS dashboard HUD, orb visualizer, and agent grid.

| Tool | Description |
|------|-------------|
| `get_hud_status` | Get Iron Man HUD theme state and 3D Orb audio metrics |
| `get_agent_dashboard` | Get multi-agent activity status (CEO, Planner, Vision, Coding agents) |
| `get_memory_explorer_data` | Get Vector DB & Knowledge Graph memory node statistics |
| `get_performance_metrics` | Get live CPU, RAM, VRAM, and LLM latency performance metrics |

---

### 📊 ObservabilitySkill
**Purpose:** Internal telemetry — cache stats, GPU VRAM, system health, and metric export.

| Tool | Description |
|------|-------------|
| `get_cache_stats` | Get dual-layer cache hit ratio, memory usage, and Redis status |
| `get_gpu_vram_status` | Get CUDA GPU VRAM usage and lazy model load allocations |
| `get_system_health` | Get CPU/RAM health, crash reports count, and active trace IDs |
| `export_telemetry_metrics` | Export aggregated telemetry metrics for diagnostics |

---

### 🌐 CrossPlatformSkill
**Purpose:** OS compatibility matrix, device pairing, and cross-device state sync.

| Tool | Description |
|------|-------------|
| `get_platform_compatibility` | Get OS details and feature compatibility matrix |
| `pair_companion_device` | Pair an Android or iOS companion app device |
| `sync_cross_device_state` | Sync clipboard or memory state to a paired companion device |
| `list_paired_devices` | List all paired companion devices |

---

### 🚀 DeploymentSkill
**Purpose:** System benchmarks, local data backup, restore, and update checking.

| Tool | Description |
|------|-------------|
| `run_system_benchmarks` | Run local performance benchmarks (CPU, latency, memory speed) |
| `trigger_backup` | Create a ZIP backup of all user data and JSON state files |
| `restore_backup` | Restore user data from a specified backup ZIP file |
| `check_update_status` | Check the current system version and update availability |

---

### 🧬 AutonomousSkill
**Purpose:** Habit learning, task prediction, long-term goal management, and self-optimization.

| Tool | Description |
|------|-------------|
| `get_learned_habits` | Get learned user habit patterns and automation suggestions |
| `predict_next_tasks` | Predict upcoming tasks based on time-of-day and habit history |
| `manage_long_term_goals` | Add or list long-term goals tracked by the Personal AI Project Manager |
| `optimize_agent_prompt` | Self-improve agent system prompts based on past conversation feedback |

---

### 🔮 ProactiveSkill
**Purpose:** Schedule background reminders and proactive environment-aware alerts.

| Tool | Description |
|------|-------------|
| `schedule_reminder` | Schedule a proactive alert at a specific date/time or interval |
| `list_reminders` | List all currently scheduled active reminders |
| `cancel_reminder` | Cancel a scheduled reminder by its numerical ID |

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

### 🧠 Prash + Ollama + Multi-Cloud Failover Setup

JARVIS uses a resilient multi-provider AI system with dynamic fallback routing designed for high availability:

1. **Primary AI Decider (Prash — Local)**
   - Custom transformer language model running locally on PyTorch CPU/GPU.
   - First-entry analysis: Decides whether a tool is required or if it can answer directly.
   - If Prash is not confident (low confidence scored via generated entropy), JARVIS automatically switches to the fallback cloud chain.

2. **Ollama & Cloud Fallback Chain**
    - If Prash falls back, or the active cloud provider is offline, JARVIS automatically switches to the next provider in the chain:
      * **Ollama API** (Local Primary Fallback, running `qwen2.5-coder:3b`)
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

#### 1. Backend Master Pytest Suite (12 Suites · 116 Tests)
```powershell
# Run the complete verified backend test suite
backend\venv\Scripts\python.exe -m pytest backend/tests/ -q
```
*Executes all 12 master test suites covering service container, intent routing, domain agents, 4-tier memory, automation executors, voice pipeline, truthful tool registry, live mode perception, and capability expansion.*

#### 2. Frontend & Route Integration Tests
```bash
cd frontend
npm test
```
*Validates Electron/React frontend components and REST routes.*

### Building for Production

```bash
cd frontend
npm run build
```

---

## 📋 Tech Stack

| Layer / Subsystem | Technologies |
|---|---|
| **Frontend HUD** | Electron + React 19 + TypeScript + Tailwind CSS + Lucide Icons + Three.js |
| **Backend Core** | Python 3.10+ + FastAPI + Uvicorn + Pydantic + Loguru |
| **LLM Inference** | Ollama (Local) + Google Gemini (`google-genai`) + Groq + OpenRouter + OpenAI |
| **Local AI Engine** | Prash Transformer (PyTorch + Custom Tokenizer) |
| **Speech & Audio** | Faster-Whisper + Edge-TTS + Piper ONNX + Windows SAPI SpVoice + OpenWakeWord |
| **Automation** | PyAutoGUI + PyWinAuto + Playwright Chromium + Win32 API |
| **Memory & Storage** | ChromaDB + SentenceTransformers + SQLAlchemy + SQLite WAL + NetworkX |
| **Vision & OCR** | OpenCV + PIL + PyTesseract + Haar Cascades |
| **Security & Sandbox** | Cryptography + PyJWT + Keyring + AST Allowlist Sandbox + EAR Blink Liveness |

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
