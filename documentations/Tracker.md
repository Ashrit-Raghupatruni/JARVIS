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

### 1.5. Extended AI OS Capabilities
* **Performance & Observability**: In-memory & Redis hybrid cache layer, CUDA VRAM scheduler with lazy model loading, and telemetry trace correlation IDs (`trace_id`).
* **Cross-Platform & Mobile Sync**: OS abstraction layer (Windows, Linux, macOS) and mobile companion app pairing engine for Android & iOS with encrypted state sync.
* **System Benchmarks & Local Backups**: Performance benchmarks runner and ZIP backup & restoration engine.
* **Autonomous Intelligence Engine**: User habit learning, predictive task execution, long-term goal planner, and self-improving prompt optimizer.

---

## 2. System Architecture Capabilities Directory

* **Security Sandbox & Vault**: Secure credential storage (Windows Credential Locker) and isolated script execution.
* **MCP Client & Server Integration**: Standardized FastMCP skill tools and dynamic tool discovery.
* **Personal Knowledge Hub (RAG)**: Local document indexing and semantic parsing (PDF, DOCX, PPTX, Markdown).
* **Performance & Observability**: Redis hybrid caching, CUDA VRAM scheduler, lazy model loading, and telemetry tracing.
* **Developer / Coding Agent**: AST code analysis, bug localization, and automated test script generation.
* **Hybrid Memory Architecture**: 6-Scope Memory System (Working, Conversational, Semantic, Procedural, Episodic, Knowledge Graph).
* **Research Agent**: Persistent browser profile manager, deep web search, citation synthesis, and fact verification.
* **Voice Intelligence**: Acoustic emotion classification, speaker profile manager, and wake word tuning.
* **Productivity Suite**: Executive daily briefings, calendar events, meeting summarizer, and task queue manager.
* **Plugin Marketplace & SDK**: Permission risk inspector, manifest loader, and dynamic plugin management.
* **User Interface & Dashboards**: Iron Man HUD, multi-agent activity dashboard, memory explorer, and performance monitor APIs.
* **Cross-Platform & Mobile Sync**: OS abstraction layer, Android/iOS companion pairing, and state sync broker.
* **Autonomous Intelligence Engine**: Workflow habit learning, predictive task execution, long-term goal manager, and self-improving prompt optimizer.
