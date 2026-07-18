# 🤖 Product Requirements Document (PRD) — JARVIS AI Desktop Assistant

## 1. Executive Summary & Vision

JARVIS is a production-grade, voice-controlled AI desktop assistant for Windows, inspired by Iron Man's home computer assistant. It is designed to act as an autonomous agent that bridges the gap between human language and Windows OS operations. Unlike standard voice assistants (which are limited to simple API lookups), JARVIS operates as a planning agent capable of executing complex, multi-step desktop tasks (opening applications, automating clicks/keystrokes, browsing the web, scraping data, running shell commands, and observing screens) with robust local-first privacy safeguards and high-speed cloud failovers.

---

## 2. Core User Personas & Use Cases

### User Personas
* **The Power User / Developer**: Wants to execute shell commands, automate repetitive GUI workflows, and run research queries hands-free.
* **The Accessibility User**: Needs complete desktop and web navigation capabilities using voice activation.
* **The Daily Briefing User**: Desires a structured morning digest of schedule, news feeds, and system stats, along with automated workstation setups.

### Primary Use Cases
1. **Hands-free OS Automation**: Opening tools, typing files, resizing windows, and running development environments via voice.
2. **Deep Desktop Research**: Launching background processes to scrape news feeds, synthesize reports, and display monitoring dashboards.
3. **Screen-Aware Reasoning**: Asking "what is on my screen right now?" to debug code, translate text, or analyze visual data.
4. **Double-Clap Workstation Triggering**: Quickly initializing standard workspace layouts (e.g., Spotify, Chrome windows, Cursor editor) through sound trigger cues without waking up voice input.

---

## 3. Functional Requirements

### 3.1. Voice Interface (STT, TTS, & Wake Word)
* **Wake Word Detection**:
  * Continual background microphone monitoring.
  * Trigger word "Hey Jarvis" parsed locally via `openwakeword`.
  * Visual chime / sound acknowledgement ("Yes, sir?") upon detection.
* **Push-to-Talk (PTT)**:
  * Keyboard shortcut `Ctrl+Space` triggers manual listening state.
* **Speech-to-Text (STT)**:
  * High-accuracy, low-latency audio transcription via local `faster-whisper`.
* **Text-to-Speech (TTS)**:
  * High-performance, natural male voice synthesis using `edge-tts`.
  * WebSocket-based audio queue to support streaming playback, interruptions, and session isolation.

### 3.2. Intelligent LLM Router & Memory
* **Provider Benchmarking**:
  * Auto-tracks response latency, throughput, token cost, and success rate for all connected LLM providers.
* **Dynamic Failover Routing**:
  * Prioritizes local execution (`Ollama` + `qwen2.5-coder:3b`) for maximum privacy and zero cost.
  * In case of timeout (30s) or provider error, automatically fails over in real-time through the provider chain: `Ollama` ➔ `Gemini` ➔ `Groq` ➔ `OpenAI` ➔ `OpenRouter`.
* **Self-Improving Memory Loop**:
  * Extracts preferences, user profile facts, and corrections from conversation transcripts.
  * Saves lessons learned to sqlite database and ChromaDB semantic cache to inject into future prompt contexts.

### 3.3. Multi-Step Agent Planner
* **Planning Engine**:
  * Translates complex user requests (e.g., "Search for AI internships, find the top 3 and save them to a file") into structured lists of execution steps (`AgentStep`).
* **Subagent Delegation**:
  * Spawns specialized agents (Automation Agent, Browser Agent, Memory Agent) to run specific subtasks.
* **UI Progress Tracking**:
  * Reports the active execution state of individual steps to the frontend in real-time.

### 3.4. Computer Control & Screen Understanding
* **GUI Automation**:
  * Window control (maximize, minimize, close), keyboard inputs, shortcuts, mouse clicks, and drag-and-drop actions.
* **Vision Processing**:
  * Capture display screenshot and send to Vision LLMs (`Gemini-2.0-Flash` / `GPT-4o`) to reason about on-screen contents.
  * Local OCR fallback using `pytesseract` to scan text without sending images to the cloud.

### 3.5. Browser Automation
* **Playwright Web Controller**:
  * Headless/headed browser navigation, form fills, button clicks, page content extraction, and google searches.

### 3.6. RSS Digests & Morning Actions
* **Morning Briefing Generator**:
  * Gathers local weather, CPU/RAM metrics, calendar events, and matches against RSS headlines (BBC, Bloomberg, CNBC, Reuters).
* **Double-Clap Trigger**:
  * Non-verbal audio activation service. When double claps are detected, executes a configured sequence: play Spotify, set up Chrome windows, launch Cursor, speak welcome greeting.

### 3.7. 3D WebGL Visualization & Hand Gestures
* **3D Animated Orb**:
  * Real-time WebGL rendering (`Three.js`) representing assistant cognitive states.
  * Transitions theme colors dynamically (Cool Cyan/Blue during standard states, Neon Orange/Amber during calculations and OS commands execution) and scales the core size and UnrealBloom glow intensity in sync with active voice amplitudes.
  * Interactive Orbit camera controls (mouse drag to rotate, scroll to zoom).
* **Hand Gesture Tracker**:
  * Local camera stream analysis using `MediaPipe Hand Landmarker` to detect hand skeletal nodes locally. No video or frame data is transmitted externally.
  * Pinch-and-drag gesture with a single hand rotates the 3D viewport.
  * Pinch-and-spread gesture with both hands zooms the camera in/out.
  * Keyboard shortcut `G` and visual HUD buttons toggle hand tracking.
  * Mirrored camera preview overlay with custom sepia color grading and tracing skeletal connections on canvas.

### 3.8. Next-Generation AI OS Foundations
* **Modular Service Manager**: Centralized registry for loading services on demand, avoiding startup locks and boosting boot efficiency.
* **Unified Event Bus**: Decentralized asynchronous messaging broker coordinating voice processing, agents, and logs.
* **Security Sandbox & Encrypted Vault**:
  * Isolated Python / terminal script execution containers restricting resource limits and command injection threats.
  * Local AES-encrypted credentials locker coupled with Windows Credential Locker.
  * Mandatory user confirmations and persistent audit logs for system modifying tools.
* **Model Context Protocol (MCP)**:
  * Unified stdin/stdout dynamic client interface mapping tools from FastMCP servers.
  * Standalone local MCP subprocesses separating tool execution from core server runtime.
* **Hierarchical Multi-Agent Engine**:
  * CEO Agent orchestrating planning delegation.
  * Worker Agent pools running collaborative parallel execution.
* **Hybrid Memory & Graph**:
  * 6-Scope Memory System (Working, Conversational, Semantic, Procedural, Episodic, and Knowledge Graph).
  * Relationship and habit tracking utilizing local NetworkX serialization.
* **Personal RAG Hub**:
  * Incremental indexing of PDFs, Markdowns, DOCX, and PPTX slide XMLs based on timestamps.
  * Cite-supported semantic searching and context injection.

---

## 4. Non-Functional Requirements

* **Performance & Latency**:
  * Local Wake Word parsing must execute within <100ms.
  * WebGL rendering must maintain a consistent 60 FPS under normal usage.
  * Failover triggers must activate immediately if a cloud provider hangs.
* **Security & Safety**:
  * Destructive commands (e.g., deleting system files, running unrecognized executables) must ask for user confirmation.
  * Local-first architecture: All standard text logs, SQLite databases, ChromaDB vector tables, and webcam frame analyses must reside strictly locally on the user's hard drive.
* **Robustness**:
  * The system must survive offline status by operating with local-only fallback dependencies (Ollama, local Whisper, Pytesseract OCR).
* **Usability & UX**:
  * High-fidelity, smooth UI animations representing states (Idle, Listening, Processing, Speaking, Executing).
  * Interactive controls must include drag-vs-click thresholds to prevent accidental assistant activation during camera rotation.
