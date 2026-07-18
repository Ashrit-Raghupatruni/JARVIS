# 📋 Project Capability Directory & System Roadmap

This document outlines the capabilities, planned system features, and architectural roadmap enhancements of the JARVIS AI Desktop Assistant.

---

## 1. System Capabilities

### 1.1. Voice & Speech System
* **Wake Word Activation**: Local parsing of "Hey Jarvis" with `openwakeword`.
* **Speech Synthesis (TTS)**: Natural male voices streaming over WebSocket via `edge-tts`.
* **Speech Recognition (STT)**: High-speed local audio transcription via `faster-whisper`.
* **Duplex Queue Handler**: Support for instant user voice interrupts.

### 1.2. Intelligent Core & Routing
* **LLM Failover Router**: Auto-selection and fallbacks across Ollama, Gemini, Groq, OpenAI, and OpenRouter.
* **Dynamic Benchmarking**: Tracking of latency, throughput, token speed, and success metrics.
* **Memory System**: Semantic knowledge search using ChromaDB and facts logging in SQLite.
* **Lessons Learned Loop**: Corrective prompt injection mechanism using past errors.
* **Local AI Engine (Prash)**: Headless custom transformer model trained on GPU to process system intents locally.

### 1.3. Desktop & Web Controls
* **GUI Control**: Window focus, application minimization, keyboard typing, cursor moving, and shortcuts using `pywinauto` and `pyautogui`.
* **Web Browser Automation**: Playwright script execution to browse, fill out forms, search, and parse pages.
* **Vision Reasoning**: Full display screenshot logging integrated with Gemini & GPT-4o Vision API.
* **Local OCR fallback**: Text extraction from screenshots using `pytesseract`.
* **LangGraph Orchestrator**: Multi-step execution loops dynamically resolving user tasks.

### 1.4. HUD Interface (UI)
* **3D Three.js WebGL Arc Reactor**: Procedural 3D wireframe model of the Arc Reactor floating, with counter-rotations, central J.A.R.V.I.S. text overlay, and voice-amplitude reactor pulsing.
* **Hand Gesture Tracking**: MediaPipe vision hand skeleton mapping via local webcam. Support for drag to spin and pinch to zoom.
* **Siri Waveform**: Dynamic audio waveform mapping.
* **Task Progress tracker**: Step-by-step checklist visualization for active agent plans.

---

## 2. Planned Features & Architectural Enhancements

* **Offline Wake Word Upgrade**: Custom wake phrase model generation to improve detection accuracy.
* **Active Context Preservation**: Saving open browser tab states and active window history across reboots.
* **Multi-Monitor Vision**: Visual support for displaying and capturing screenshots across individual displays dynamically.
* **Calendar & Email Integration**: Direct calendar hooks and email drafts creation via voice.
* **Companion Mobile App**: Remote microphone relay to trigger desktop shortcuts and control JARVIS from a local Wi-Fi network.

---

## 3. System Architecture & Foundation Roadmap

* **Security Sandbox & Vault**:
  * Secure credential storage (Windows Credential Locker).
  * Isolated Docker environment for Coding and Browser script execution.
* **MCP Client & Server Integration**:
  * Refactor standard skills to standard FastMCP servers.
  * Implement dynamic tool discovery client in the backend.
* **Personal Knowledge Hub (RAG)**:
  * Local document indexing and semantic parsing (PDF, Markdown, Obsidian).
* **Performance Optimization**:
  * Redis caching, lazy model loading, and async queue tuning.
* **Developer / Coding Agent**:
  * Auto-bug localization, file refactoring, and test script generation.
* **Hybrid Memory Architecture**:
  * Split context storage (Working, Short-Term, Episodic, and Procedural).
* **Knowledge Graph**:
  * Relationship tracking and preference extraction.
* **Multi-Agent Collaboration**:
  * CEO-to-Planner-to-Worker event loop coordination.
* **Context Awareness Engine**:
  * Real-time window and desktop activity tracking.
* **Vision-Based Computer Use**:
  * Accessibility Tree parser + fallback visual coordinates (UI-TARS/OmniParser).
* **Workflow Learning Engine**:
  * Record/replay user macros and auto-generate system automations.
* **Autonomous Background Agents**:
  * Asynchronous execution of long-running objectives.
* **Research Agent**:
  * Deep multi-source citation and web scraping report compiler.
* **Plugin Marketplace**:
  * Sandboxed community plugin installer and permission dashboard.
* **Cross-Platform Ecosystem**:
  * macOS and Linux porting, and companion mobile relay applications.
