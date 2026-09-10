# 📄 Product Requirements Document (PRD) — JARVIS AI OS

**Project Name:** J.A.R.V.I.S. (Just A Rather Very Intelligent System)  
**Author:** Ashrit Raghupatruni  
**Version:** 3.5.0  
**Last Updated:** August 8, 2026

---

## 1. Product Overview & Vision

JARVIS is a production-grade, local-first Personal AI Operating System designed to function as an autonomous technical co-pilot. It combines local LLMs (Ollama, Prash) with cloud fallback providers (Gemini, OpenRouter, Groq, NVIDIA NIM), real-time desktop UI perception, full terminal and browser automation, cybernetic HUD/Arc Reactor visuals, an Autonomous Agent Ecosystem with multi-day SQLite WAL goal checkpointing, and fail-closed security gatekeeping.

---

## 2. Key Product Capabilities

### 1. Asset-Based 3D Face Avatar Engine (`facecap.glb`)
- Uses official `facecap.glb` 3D face scan model asset with built-in ARKit morph targets.
- Speech amplitude viseme lip-sync mapped to `blendShape1.jawOpen`.
- Natural double-blinking mapped to `blendShape1.eyeBlink_L` & `blendShape1.eyeBlink_R`.
- 360-degree continuous Y-axis rotation toggle.
- Styled with high-contrast Green Hacker PBR material (`#00ff66`). Zero procedural geometry fallbacks.

### 2. Autonomous Agent Ecosystem
- **Multi-Agent Orchestration**: Spawns isolated task instances (`SubAgentInstance`) for specialized roles (`CodeAgent`, `ResearchAgent`, `SecurityAgent`).
- **Inter-Process Communication (IPC)**: Bi-directional message bus supporting agent requests, responses, and security policy audits.
- **Long-Horizon Goal Checkpointing**: Persistent SQLite WAL `goal_queue` and `agent_checkpoints` recording multi-day task progress in `data/jarvis.db`.
- **KV-Cache Context Pruning**: Context window compression service (`KVCachePruner`) saving >24% token space.
- **Autonomous Agent Studio**: 4-quadrant UI dashboard under `☰ Command Center ▾` for monitoring active sub-agents, IPC logs, goal timelines, and token savings.

### 3. Fail-Closed Mobile & Desktop Security
- Mobile companion JWT authentication fails closed (`verify_token` returns `None` on any decode error).
- Development token prefixes (`DEV_TOKEN_`) strictly gated behind `settings.DEBUG == True`.
- Mobile Gatekeeper Desktop Exit Interlock requiring explicit mobile companion approval before laptop OS exit.
- Speaker and facial biometric verifications fail closed (`verified: False`, `confidence: 0.0`) when reference embeddings are uncalibrated or missing.

---

## 3. UI/UX Specifications
- **Navigation**: Single unified top header dropdown (`☰ Command Center ▾`).
- **Visual Modes**: Auto-switching between Idle Tech-Ring HUD (standby) and 3D Talking Face Avatar (speaking), with manual lock buttons.
- **Theme**: Green Hacker Aesthetic (`#00ff66` accent on `#050d08` dark emerald glass background).

---

## 4. Unified Production Capabilities & Reliability Guarantees (v3.6.0 Master Resolution)

### 1. High-Performance Deterministic & Neural Decision Pipeline
- **Ultra-Fast Regex Triage**: Compiled deterministic matchers handle high-frequency OS commands in `0.0083ms`.
- **Prash Neural Engine Grounding**: Injects active window context, process ID, and personal memory facts into neural prompt synthesis with semantic anti-hallucination validation.

### 2. Full-Desktop Computer Control & Accessibility Tree Integration
- **Chromium DOM Accessibility**: Launches Chrome/Edge with `--force-renderer-accessibility` for native UIA inspection without extensions.
- **Safety Coordinate Clamping**: Clamps cursor coordinates away from screen corners `(0, 0)` to prevent PyAutoGUI failsafe exceptions.
- **Viewport Scroll-and-Search**: Adaptive Tier 4 scrolling loop locates and clicks controls positioned below the initial viewport fold.
- **Window Settle Gating**: Enforces 0.5s settle window wait after application launch to guarantee focus readiness.

### 3. Document, Resume & Personal Memory Intelligence
- **Disk-Grounded Resume Processing**: Directly indexes and extracts facts from real PDF resume files using PyPDF and Tesseract OCR fallback.
- **Dynamic User Fact Resolution**: Replaces mock profile data with verified user identity, contact details, and education from `MemoryService`.
- **ChromaDB Memory Pruning**: Supports explicit fact forgetting and deletion from vector store and SQLite memory logs.

### 4. Real-Time Sub-Second Voice OS
- **Local SAPI Prioritization**: Delivers speech synthesis in `213.1ms` via Windows native SAPI `SpVoice`, eliminating cloud network delays.
- **Conversational Barge-In & Preemption**: Cancels running planner tasks and purges work queues immediately upon voice interruption.

### 5. Universal Safety Gatekeeper & 56-Tool Production Registry
- **Universal Policy Enforcement**: Intercepts remote mobile shutdowns, local script executions, and n8n webhooks through fail-closed policy checks.
- **Expanded Tool Catalog**: 56 production tools registered, verified, and exposed via REST (`/api/tools`) and WebSocket interfaces.

---

## 5. Expanded Multimodal & Domain Intelligence PRD Requirements (Added September 8, 2026)

### 1. Asynchronous Multimodal Generation Infrastructure
- **Job Lifecycle Queue**: Dedicated background asynchronous queue with SQLite WAL persistence (`data/generation_jobs.db`) and unique UUID tracking.
- **Fail-Closed Adapters**: Strict preflight checking for Image (Local GPU / Stability AI), Video (SVD / Runway), and 3D mesh (Three.js / Meshy / Tripo3D) APIs. No decorative simulations allowed.
- **Progress Tracking**: Sub-50ms polling endpoints (`/api/ui/generation/status/{id}`) and listing endpoints (`/api/ui/generation/jobs`).

### 2. Specialized Intelligence Domains & Tools
- **Chemoinformatics & Life Sciences**: Parsing molecular stoichiometry, molar masses, balancing chemical reactions, querying NCBI PubChem database, and biological pathway generation.
- **Safe SQL & Developer Automation**: Read-only AST validation enforcing that natural language SQL translation never executes destructive operations (`DROP`, `DELETE`, `UPDATE`, `ALTER`). Python docstring generation across Google/NumPy/Sphinx styles.
- **Productivity & Note Management**: Direct Markdown file persistence under `data/notes/` and multi-channel copywriting generation.
- **UI Design & Web Scaffolding**: Layout critique against WCAG 2.1 standards, Tailwind palette generation, and standalone component scaffolding.
- **Vision Intelligence**: Haar cascade / contour object detection with grounded image captioning.
- **Desktop RPA & Audio Intelligence**: Step-isolated RPA macro playback, neural Edge-TTS voice generation, and procedural waveform SFX synthesis.

### 3. Response-Length Discipline
- Default LLM planner prompts enforce concise 1–3 sentence responses with structured bullet points for maximum operational efficiency, only expanding into detailed reports upon explicit user request.


