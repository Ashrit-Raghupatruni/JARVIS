# 📐 Technical Specification (TechSpec)

This document provides the high-level technical specifications, stack requirements, component boundaries, and performance benchmarks for JARVIS. **Last Updated:** July 31, 2026

---

## 1. Technology Stack Specification

| Layer | Technologies & Frameworks |
|---|---|
| **Frontend Framework** | React 18, TypeScript 5, Vite, Electron 30, TailwindCSS, Lucide Icons |
| **3D Render Engine** | Three.js (r164), WebGL 2, `GLTFLoader`, `MeshoptDecoder`, Custom PBR Shaders |
| **3D Asset** | `facecap.glb` (332.8 KB, Three.js dev examples) with ARKit morph targets |
| **Backend Core** | Python 3.10, FastAPI, Uvicorn, Asyncio Event Loop, Loguru |
| **Database** | SQLite3 with WAL (Write-Ahead Logging) and FTS5 Full-Text Search |
| **Agent Ecosystem** | `AgentEcosystemService`, `SubAgentInstance`, `LongHorizonCheckpointService`, `KVCachePruner` |
| **Security & Auth** | PyJWT (`HS256`), `SafetyService` Regex Policy Engine, Gatekeeper Mobile Interlock |

---

## 2. Component Boundaries & API Interconnects

```
 ┌────────────────────────────────────────────────────────────────────────┐
 │                      React / Electron Renderer                         │
 │  - Hero Visualizer (IdleHUD.tsx / TalkingFace3D.tsx)                   │
 │  - Nav Bar (☰ Command Center ▾ Dropdown)                               │
 │  - AutonomousAgentStudio.tsx (Sub-agents, IPC logs, Goals, Pruner)     │
 └───────────────────────────────────┬────────────────────────────────────┘
                                     │ WebSocket / REST API
 ┌───────────────────────────────────▼────────────────────────────────────┐
 │                          FastAPI Backend Core                          │
 │  - ServiceManager Registry                                             │
 │  - AgentEcosystemService <--> SubAgentInstance <--> PlannerAgent      │
 │  - LongHorizonCheckpointService (data/jarvis.db SQLite WAL)            │
 │  - KVCachePruner <--> LLMService                                       │
 │  - MobileAuthService (Fail-Closed JWT & Gatekeeper Interlock)          │
 └────────────────────────────────────────────────────────────────────────┘
```
