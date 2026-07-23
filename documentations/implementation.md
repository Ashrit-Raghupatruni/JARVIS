# 🏗️ Implementation Architecture & Component Breakdown

This document provides a deep dive into the code structure, file layouts, startup execution sequence, and background services in JARVIS. **Last Updated:** July 23, 2026

---

## 1. Project Directory Structure

```
JARVIS/
├── backend/
│   ├── api/
│   │   ├── middleware.py    # CORS allow_origins=["*"] & request logger
│   │   ├── mobile_router.py # Mobile companion REST API (/api/v1/mobile)
│   │   ├── mobile_ws.py     # Mobile companion real-time WebSocket stream (/api/v1/mobile/ws)
│   │   ├── routes.py        # Desktop REST endpoints (health, status, history, settings, etc.)
│   │   └── websocket.py     # Main WebSocket duplex router (/ws)
│   ├── agents/
│   │   ├── langgraph_agent/ # LangGraph tool-calling agent module
│   │   ├── multi_agent/     # CEO-Planner-Worker orchestrators
│   │   ├── planner.py       # Central agent running tools or LLM fallback
│   │   └── voice.py         # Handles voice stream loop processing
│   ├── models/
│   │   ├── database.py      # Async SQLAlchemy SQLite model classes
│   │   ├── schemas.py       # Pydantic validation models
│   │   └── mobile_schemas.py# Pydantic mobile schemas (SystemTelemetry, ScreenPreview, Approval)
│   ├── services/
│   │   ├── perception/
│   │   │   ├── uia_scene_graph.py  # Sub-30ms Win32 UIA structured scene graph extractor
│   │   │   └── spatial_engine.py   # Multi-monitor bounds & spatial reference anchor engine ("this/that")
│   │   ├── live_mode/
│   │   │   ├── live_engine.py      # 1.0 FPS background observation loop & LiveContextFrame generator
│   │   │   └── form_assistant.py   # Smart form parser, profile auto-filler & pre-submission validator
│   │   ├── experience_engine.py # Action trace logger & SQLite WAL database (experiences.db)
│   │   ├── reflection_engine.py # Post-task self-evaluation & procedural strategy generator
│   │   ├── self_healing.py      # Runtime fault detector, auto-recovery & fallback cascade
│   │   ├── strategy_memory.py   # Procedural memory & dynamic confidence scoring
│   │   ├── skills/
│   │   │   └── skill_library.py # Dynamic skill synthesis & OS operational modes (Coding, Gaming, Work, Research)
│   │   ├── mobile_auth.py    # Device pairing, 6-digit PIN, trusted_devices.json, JWT
│   │   ├── mobile_gateway.py # Real-time telemetry, mobile approval gatekeeper, screen preview
│   │   ├── mobile_bridge.py  # Telegram bot push gateway & fallback notification bridge
│   │   ├── uia_engine.py     # Native Win32 Accessibility UI Automation engine with pattern invocation
│   │   ├── file_indexer.py   # SQLite FTS5 sub-second natural language file indexer
│   │   ├── automation.py    # Desktop GUI automation wrapper
│   │   ├── browser.py       # Playwright browser manager
│   │   ├── hybrid_memory_system.py # Memory graph builder with SQLite WAL mode
│   │   ├── rag_service.py   # RAG document parsing & vector matching with WAL mode
│   │   ├── llm.py           # Model bindings wrapper for APIs & local Ollama
│   │   ├── llm_router.py    # Metric analyzer & fallback router
│   │   ├── manager.py       # ServiceManager lifecycle registry
│   │   └── memory.py        # SQLite WAL + ChromaDB semantic cache
│   └── main.py              # FastAPI lifespan launcher & service registration (bound to 0.0.0.0:8000)
│
├── mobile_app/              # Dedicated Native Android Companion App
│   └── android/             # Native Android Java wrapper project
│       └── app/src/main/
│           ├── AndroidManifest.xml # networkSecurityConfig & usesCleartextTraffic="true"
│           ├── assets/companion.html # Material 3 8-Tab Mission Control UI Dashboard
│           ├── java/com/jarvis/companion/MainActivity.java # WebSettings with universal file access
│           └── res/xml/network_security_config.xml # Cleartext HTTP/WS permit for local Wi-Fi
│
└── frontend/                # React + Electron Desktop Shell
    ├── src/main/index.ts    # BrowserWindow setup & uvicorn process spawner (--host 0.0.0.0)
    └── src/renderer/src/
        ├── components/Orb.tsx # WebGL 3D Arc Reactor (Battery Saver visibility listener)
        └── components/DashboardLayout.tsx # Adaptive Responsive Fullscreen vs Compact Orb HUD
```

---

## 2. Service Manager Lifecycle & Initialization Sequence

During application startup in [`backend/main.py`](file:///c:/Users/ashri/JARVIS/backend/main.py), services initialize in strict dependency order:

1. **Database & Storage Services**:
   - `MemoryService` initializes SQLite database with `PRAGMA journal_mode=WAL;` and ChromaDB vector collections.
   - `FileIndexerService` initializes SQLite FTS5 virtual tables at `data/file_index.db`.
2. **Desktop & Automation Services**:
   - `UIAEngine` binds to Win32 Accessibility APIs.
   - `DesktopAutomationService` registers GUI actions.
3. **Mobile Gateway & Security Services**:
   - `MobileAuthService` loads trusted device registrations from `data/trusted_devices.json`.
   - `MobileGatewayService` prepares system telemetry collectors & approval event queues.
   - `MobileBridgeService` binds Telegram push gateway for remote alerts.
4. **Agent & Voice Engines**:
   - `STTService` pre-loads local faster-whisper model in background.
   - `PlannerAgent` registers standard skill tools and UIA selectors.
5. **FastAPI & WebSockets**:
   - Exposes `/api/v1/mobile` REST routes and `/api/v1/mobile/ws` WebSockets bound to `0.0.0.0:8000`.

---

## 3. Mission Control REST & WebSocket Route Directory

| Endpoint | Method / Protocol | Description | Target Service |
|---|---|---|---|
| `/api/v1/mobile/pair` | POST | Pair companion app with 6-digit PIN | `MobileAuthService` |
| `/api/v1/mobile/telemetry` | GET | Stream CPU, RAM, GPU, Disk, Battery, Task | `MobileGatewayService` |
| `/api/v1/mobile/screen/preview` | GET | On-demand desktop screenshot thumbnail | `PIL.ImageGrab` / `pyautogui` |
| `/api/v1/mobile/system/command` | POST | Execute Shutdown, Restart, Lock, Open App | `SystemSkill` |
| `/api/v1/mobile/approvals/respond` | POST | Submit Security Gatekeeper decisions | `MobileGatewayService` |
| `/api/v1/mobile/diagnostics` | GET | Run self-health check across all components | `ObservabilityService` |
| `/api/v1/mobile/brain/memory` | GET | Fetch long-term memories & knowledge graph | `HybridMemorySystem` |
| `/api/v1/mobile/tasks/queue` | GET | Fetch Task Queue state (pending, running) | `TaskQueueService` |
| `/api/v1/mobile/apps/running` | GET | Inspect running desktop applications | `psutil` |
| `/api/v1/mobile/files/search` | GET | Search files using SQLite FTS5 indexer | `FileIndexerService` |
| `/api/v1/mobile/ws` | WebSocket | Real-time bi-directional telemetry & chat stream | `handle_mobile_ws()` |
