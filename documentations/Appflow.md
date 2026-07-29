# 🔄 Application Flow & Execution Sequences

This document maps out the operational lifecycles, message-passing flows, state machines, and visual navigation interactions within the JARVIS personal AI OS ecosystem. **Last Updated:** July 29, 2026

---

## 1. Unified Navigation & Mode Switcher Flow

The top header bar consolidates all navigation into a single dropdown menu (`☰ Command Center ▾`), while the main hero visualizer panel automatically transitions between the **Idle Tech-Ring Circular HUD** and the **Asset-Based 3D Talking Face Avatar** based on speech state or manual user lock.

```mermaid
flowchart TD
    A[Electron Main Window Launch] --> B[Zustand App Store Init]
    B --> C[Top Header Bar: ☰ Command Center Dropdown]
    
    C -->|Select Option| D{Dropdown Selection}
    D -->|Command Center| E[Resizable 70/30 Hero Visualizer + Chat Panel]
    D -->|Chat History| F[Session Conversation Message Log]
    D -->|Workflow Studio| G[Visual Drag-and-Drop Workflow Builder]
    D -->|Task Queue| H[Task Queue Manager & Scheduler]
    D -->|Telemetry| I[Hardware Gauges & LLM Providers]
    D -->|Live Mode| J[Live Vision Perception & WebCam Stream]
    D -->|Automation| K[Computer Use & Playwright Browser]
    D -->|Debug Inspector| L[Live Debug Log & System Telemetry]
    
    E --> M{Visual Mode Switcher}
    M -->|AUTO DISPLAY| N[Idle HUD in Standby -> 3D Talking Face during TTS Speech]
    M -->|HUD LOCK| O[Lock Display to Idle Tech-Ring HUD]
    M -->|3D FACE LOCK| P[Lock Display to Asset-Based 3D Talking Face Avatar]

    P --> Q[3D ROTATION TOGGLE: ON / OFF Button]
    Q -->|ON| R[Smooth 360-Degree Continuous Y-Axis Rotation]
    Q -->|OFF| S[Freeze Rotation in Position while Viseme Speech Lip-Sync Continues]
```

---

## 2. 3D Face Engine Rendering & Viseme Speech Flow

```mermaid
sequenceDiagram
    participant User as User / TTS Service
    participant WebAudio as Web Audio API AnalyserNode
    participant Store as Zustand App Store
    participant FaceEngine as FaceRenderer (32-bit Float Pass)
    participant LipSync as VisemeLipSync Controller
    participant IdleAnim as NaturalIdleAnimator
    participant WebGL as Three.js Canvas (60 FPS)

    User->>WebAudio: Stream TTS Audio Buffer (Speech Active)
    WebAudio->>Store: Update audioLevel (0.0 to 1.0) & set assistantState='speaking'
    Store->>FaceEngine: Render loop frame update (dt, elapsed)
    
    FaceEngine->>LipSync: evaluateFromAudio(audioLevel)
    LipSync-->>FaceEngine: Viseme Weights (jawOpen, viseme_aa, viseme_E, viseme_O, etc.)
    FaceEngine->>FaceEngine: Apply viseme weights to GLTF headMesh morphTargetInfluences
    
    FaceEngine->>IdleAnim: update(dt, elapsed, rootGroup, headMesh, is3DRotationEnabled)
    Note over IdleAnim: Evaluates chest/neck breathing sway,<br/>procedural double-blinking, and 360° Y-axis rotation
    
    FaceEngine->>WebGL: Render frame with ACES Filmic Tonemapping & Studio 3-Point Lighting
```

---

## 3. Workstation Initialize Flow (Double-Clap Trigger)

The `ClapService` listens continuously in the background using a lightweight audio thread. It detects physical claps by looking for high peak-to-average power ratios (PAPR) and triggers automated setup tasks without waking up the LLM speech loop.

```mermaid
sequenceDiagram
    participant Mic as Hardware Microphone
    participant ClapS as ClapService (Background Thread)
    participant OS as Windows OS / Spotify / Chrome
    participant TTS as TTS Service (edge-tts)
    participant UI as Electron Frontend
    
    ClapS->>Mic: Open audio input stream (PyAudio)
    Mic->>ClapS: Stream raw audio buffers
    Note over ClapS: Analyzes buffer amplitude peaks.<br/>Detects 2 distinct peaks within 0.1s to 0.5s window.
    ClapS->>UI: Emit IPC event 'double-clap-detected'
    UI->>OS: Execute startup chain (Play Spotify, launch Chrome panel layouts, activate Cursor IDE)
    ClapS->>TTS: Invoke ElevenLabs / Edge-TTS welcome greeting
    TTS->>UI: Stream welcome speech audio
    UI->>User: Play welcome audio greeting
```

---

## 4. Autonomous Web Agent Interaction Sequence Flow

```mermaid
sequenceDiagram
    participant User as User Speech / Chat
    participant Agent as PlannerAgent / ToolRegistry
    participant Browser as BrowserService (Playwright)
    participant DOM as DOM Element Indexer
    participant LLM as LLM Decision Cascade

    User->>Agent: "Search for Quantum Computing founding year and tell me history"
    Agent->>Browser: run_browser_agent(task)
    loop Perceive-Decide-Act-Observe Step
        Browser->>DOM: perceive_page_state()
        DOM-->>Browser: Interactive element tree [a, button, input]
        Browser->>LLM: Evaluate next action (Navigate / Type / Extract)
        LLM-->>Browser: Chosen action step
        Browser->>DOM: Execute action (click/type/navigate)
        Browser->>DOM: Observe page state change
    end
    Browser-->>Agent: Action execution log & extracted page text
    Agent-->>User: Final refined response
```

---

## 5. Dedicated Android Mobile Companion Pairing & Gatekeeper Flow

```mermaid
sequenceDiagram
    participant User as User (Phone)
    participant App as Android Companion App
    participant API as FastAPI Mobile Gateway (/api/v1/mobile)
    participant Auth as MobileAuthService
    participant Gate as MobileGatewayService
    participant Store as trusted_devices.json
    
    User->>App: Enter PIN "236786" & tap [Connect to JARVIS]
    App->>API: POST /api/v1/mobile/pair {pin, device_name, device_id}
    API->>Auth: Validate PIN via easy_pair()
    Auth->>Store: Register device in trusted_devices.json
    Auth-->>App: Issue signed 1-year JWT Bearer Access Token
    App->>API: Open WebSocket /api/v1/mobile/ws?token=...
    API->>Gate: Accept WS connection immediately (101 Switching Protocols)
    Gate-->>App: Stream 2s Telemetry Heartbeat (CPU, RAM, GPU, Battery, Task)
```
