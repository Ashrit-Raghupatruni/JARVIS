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
