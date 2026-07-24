# 🛠️ Technical Specification — JARVIS Architecture & Technologies

## 1. System Overview

JARVIS is built as a split-architecture personal AI OS:
1. **Frontend Desktop (Presentation Layer)**: An Electron-based shell wrapping a React 19 application with a 3D WebGL Arc Reactor Orb, Visual Workflow Studio, and Task Queue Manager.
2. **Dedicated Mobile Companion App**: Native Android App wrapper ([`mobile_app/android/`](file:///c:/Users/ashri/JARVIS/mobile_app/android/)) hosting an 8-Tab Material 3 Dark-Theme Mission Control Dashboard ([`companion.html`](file:///c:/Users/ashri/JARVIS/mobile_app/android/app/src/main/assets/companion.html)) connecting via secure HTTPS REST API and WebSockets (`0.0.0.0:8000`).
3. **Backend Engine (Application & Intelligence Layer)**: A FastAPI application running locally bound to `0.0.0.0:8000`. It manages speech services, multi-provider LLM fallback routing, native Win32 accessibility UI automation, SQLite FTS5 file search, and mobile security gatekeeping.

```mermaid
graph TD
    User([User]) <-->|Voice/UI| Frontend[Electron + React UI]
    Phone([Android Phone]) <-->|REST & WS 8000| Backend[FastAPI Server - 0.0.0.0:8000]
    
    subgraph Backend Services
        Auth[MobileAuthService]
        Gate[MobileGatewayService]
        UIA[UIAEngine - Win32]
        FTS[FileIndexerService - FTS5]
        Router[LLM Router]
        Planner[PlannerAgent]
        MemoryService[Memory & Vector RAG]
        ExpEngine[ExperienceEngine]
        ReflEngine[ReflectionEngine]
        SelfHealing[SelfHealingEngine]
        StratMemory[StrategyMemoryService]
        LiveEngine[LiveModeEngine - 1.0 FPS Perception Loop]
        SceneGraph[UIASceneGraph - Win32 UIA Parser]
        SpatialEngine[SpatialEngine - Multi-Monitor Engine]
        FormAssistant[FormAssistant - Smart Form Parser]
        STT[Faster-Whisper STT]
        TTS[Edge-TTS Engine]
    end
    
    Backend <--> Auth
    Backend <--> Gate
    Backend <--> UIA
    Backend <--> LiveEngine
    Backend <--> SceneGraph
    Backend <--> SpatialEngine
    Backend <--> FormAssistant
    Backend <--> FTS
    Backend <--> Router
    Backend <--> STT
    Backend <--> TTS
    Backend <--> MemoryService
    Backend <--> ExpEngine
    Backend <--> ReflEngine
    Backend <--> SelfHealing
    Backend <--> StratMemory
    
    subgraph Databases
        SQLite[(SQLite WAL Mode)]
        Chroma[(ChromaDB Vector Store)]
    end
    
    MemoryService <--> SQLite
    MemoryService <--> Chroma
```

---

## 2. Technical Stack Details

### 2.1. Mobile Gateway & Android Mission Control
* **Mobile Router & WebSockets**: `mobile_router.py` & `mobile_ws.py` handling PIN pairing, device JWT authentication, live telemetry streaming, remote system commands (`shutdown`, `restart`, `lock`), screen preview thumbnails, and 8-tab Mission Control navigation.
* **Mobile Security Gatekeeper**: `MobileGatewayService` pausing dangerous desktop operations (`asyncio.Event`) until resolved via mobile push notification.
* **Android Shell Security**: Configured [`network_security_config.xml`](file:///c:/Users/ashri/JARVIS/mobile_app/android/app/src/main/res/xml/network_security_config.xml) and `setAllowUniversalAccessFromFileURLs(true)` in [`MainActivity.java`](file:///c:/Users/ashri/JARVIS/mobile_app/android/app/src/main/java/com/jarvis/companion/MainActivity.java#L28) allowing local cleartext HTTP/WebSocket connections on Wi-Fi network `0.0.0.0:8000`.

### 2.2. Desktop UI Automation & Natural Language File Indexing
* **Native Win32 Accessibility Automation**: `UIAEngine` wrapping Win32 accessibility controls to locate and interact with desktop applications resolution-independently.
* **Sub-second File Indexer**: `FileIndexerService` employing SQLite Full-Text Search (FTS5) virtual tables for searching local workspace files.

### 2.3. Database Concurrency & WebGL Battery Throttling
* **SQLite WAL Mode**: Enforced `PRAGMA journal_mode=WAL;` across all connections (`MemoryService`, `RAGService`, `FileIndexerService`).
* **WebGL Battery Saver**: `visibilitychange` listener in `Orb.tsx` pauses WebGL rendering loops when window is obscured or minimized.

### 2.4. 6: Next-Gen Upgrades & Live Mode Core (100% Completed)
* **Offline GGML Speech & 4-Bit GGUF Quantization**: `backend/prash/engine.py` supports 4-bit GGUF quantization and offline GGML `faster-whisper` STT.
* **Multi-Device Peer-to-Peer Mesh Syncing**: `SyncService` (`sync_service.py`) handles UDP broadcast discovery & Fernet encrypted P2P datachannel mesh syncing.
* **Autonomous Workflow Learning & Macro Recording**: `AutonomousEngineService` (`autonomous_engine.py`) records desktop UI interactions and synthesizes Python macro scripts.
* **Biometric Face & Voice Speaker Verification**: `VoiceIntelligenceService` (`voice_intelligence.py`) provides local speaker embedding identification (`verify_speaker_biometrics`) and facial recognition camera login (`verify_face_biometrics`).
* **Edge RAG Knowledge Graph Visualizer**: `HybridMemorySystem` (`hybrid_memory_system.py`) exports NetworkX 3D Knowledge Graph representation of episodic, semantic, and working memories.
* **Dedicated Live Mode Core**: `LiveModeEngine` (`backend/services/live_mode/`) runs a low-latency 1.0 FPS perception loop emitting structured `LiveContextFrame`s with workflow classification, next-step guidance, smart form auto-fill with pre-submission validation, and multi-monitor workspace layout restorer.

---

## 3. Future Technical Specifications & Architecture (7–13)

### 3.1. 7: Autonomous Agent Ecosystem
* **Sub-Agent Thread Isolation**: Sandboxed child sub-agents (`CodeAgent`, `ResearchAgent`, `SecurityAgent`) executing in isolated process pools communicating over an internal IPC JSON-RPC bus.
* **Context Compression & Pruning**: Rolling KV-cache pruning and semantic chunking algorithm to sustain infinite context windows during multi-day task executions.

### 3.2. 8: Predictive & Proactive Intelligence
* **Behavioral Pattern Mining Engine**: Time-series routine analyzer mining daily desktop action traces (`ExperienceEngine`) to pre-launch applications and stage workspaces before explicit user commands.
* **Ambient Multi-Modal Presence**: Integrates webcam OpenCV gaze estimation and Bluetooth RSSI proximity for zero-touch user login, desktop lock/unlock, and emotion-adapted TTS audio synthesis.

### 3.3. 9: External Ecosystem Integration
* **Universal API Connector Vault**: AES-256 encrypted token store managing OAuth2 refresh tokens for 100+ external SaaS services with dynamic Python request code generation.
* **Smart Home IoT Bridge**: Local Matter/Thread protocol controller interfacing with Home Assistant MQTT entities and mobile GPS geofencing triggers.

### 3.4. 10: Security & Privacy Hardening
* **Homomorphic RAG Memory Queries**: TenSEAL homomorphic encryption allowing RAG semantic search over encrypted embeddings without memory decryption.
* **TPM / Secure Enclave Key Isolation**: System hardware enclave integration for JWT signing keys, face embedding vectors, and user biometric tokens.

### 3.5. 11: Advanced Interaction Modes
* **Spatial Computing WebXR Bridge**: 3D spatial UI streaming WebXR passthrough overlay for Apple Vision Pro & Meta Quest headsets with 3D hand-tracking drag-and-drop.
* **Multi-User Profile Memory Spaces**: Voice-biometric profile switching maintaining isolated working and episodic memory partitions.

### 3.6. 12: Performance & Acceleration
* **TensorRT & NPU Offloading**: Execution pipelines utilizing Intel AI Boost, Apple Neural Engine, and Qualcomm Hexagon NPUs for sub-10ms embedding and STT processing.
* **Distributed LAN Cluster VRAM**: Model layer splitting across local network devices (Laptop GPU + Desktop GPU + Mobile NPU) forming a unified VRAM pool.

### 3.7. 13: Developer Platform
* **WASM Plugin Sandbox**: WebAssembly execution environment running third-party plugins safely.
* **Dynamic LoRA Merger**: Real-time runtime LoRA adapter merging combining domain-specific weights (coding + creative + personal memory).
