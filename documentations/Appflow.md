# 🔄 Application Flow & Execution Sequences

This document maps out the operational lifecycles, message-passing flows, and state machines within the JARVIS desktop ecosystem.

---

## 1. Workstation Initialize Flow (Double-Clap Trigger)

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

## 2. Wake Word Activation Flow

```mermaid
sequenceDiagram
    participant User as User
    participant Mic as Hardware Microphone
    participant Wake as WakeWordService (openwakeword)
    participant UI as Electron/React Frontend
    participant WS as WebSocket Controller (/api/voice)
    
    Note over Wake: Continuously streams from mic<br/>when JARVIS is in IDLE state.
    User->>Mic: "Hey Jarvis"
    Mic->>Wake: Raw audio stream
    Wake->>Wake: Match embeddings against "Hey Jarvis" model
    Wake->>UI: Trigger wake word event
    UI->>UI: Play chime sound (activation notification)
    UI->>WS: Transition state to 'listening'
    UI->>User: Highlight JARVIS Orb (Spins & glows)
```

---

## 3. Voice Request & Execution Loop

This diagram details a complete multi-step task execution from voice input to subagent execution.

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant UI as Electron/React Frontend
    participant WS as WebSocket Connection
    participant BE as FastAPI Backend
    participant STT as Whisper STT Service
    participant Router as LLM Provider Router
    participant Agent as Planner Agent
    participant Tool as System Automation (Playwright / PyAutoGUI)
    participant TTS as Edge-TTS Service

    User->>UI: Speaks: "Search for AI news and tell me the top headline"
    UI->>WS: Stream raw PCM audio chunks
    WS->>BE: Forward raw audio buffer
    BE->>STT: Process buffer chunks
    STT->>BE: Return transcribed text: "Search for AI news..."
    BE->>WS: Send TranscriptMessage (type: "transcript")
    WS->>UI: Update chat UI with typed user message
    
    BE->>Router: Forward prompt query
    Note over Router: Checks provider stats.<br/>Selects Ollama (Local) as primary.
    Router->>BE: Return LLM client connection
    
    BE->>Agent: Parse request and generate execution plan
    Agent->>BE: Return structured plan: [Step 1: Browse Google, Step 2: Extract text, Step 3: Summarize]
    BE->>WS: Send AgentTask plan details (type: "agent_task")
    WS->>UI: Render steps in TaskProgress widget
    
    loop For each step in plan
        BE->>Agent: Execute Step 1 (Tool: Browser / Playwright)
        Agent->>Tool: Execute browser search
        Tool-->>Agent: Return crawled web text
        BE->>WS: Send Progress Update (type: "agent_progress")
        WS->>UI: Update Step 1 Status
    end
    
    Agent->>Router: Formulate final response with data
    Router-->>Agent: Return synthesized text response
    BE->>WS: Send final text response (type: "response")
    WS->>UI: Append JARVIS text reply to chat log
    
    BE->>TTS: Generate audio speech
    TTS-->>BE: Stream MP3 audio segments
    BE->>WS: Stream TTSAudioMessage chunks (type: "tts_audio")
    WS->>UI: Play audio stream and animate VoiceWave widget
```

---

## 4. LLM Routing & Failover State Machine

When a query is dispatched, the `LLMRouter` checks the availability of Ollama. If it fails, it cascades through the cloud providers.

```mermaid
stateDiagram-v2
    [*] --> CheckOllama: Dispatch Query
    
    CheckOllama --> LocalExecution: Ollama online & responsive (<30s)
    LocalExecution --> LogSuccess: Return Output
    
    CheckOllama --> RouteGemini: Ollama offline/timeout
    RouteGemini --> CloudExecution_Gemini: Gemini API online
    CloudExecution_Gemini --> LogSuccess: Return Output
    
    RouteGemini --> RouteGroq: Gemini API error/rate-limit
    RouteGroq --> CloudExecution_Groq: Groq API online
    CloudExecution_Groq --> LogSuccess: Return Output
    
    RouteGroq --> RouteOpenAI: Groq API error
    RouteOpenAI --> CloudExecution_OpenAI: OpenAI API online
    CloudExecution_OpenAI --> LogSuccess: Return Output
    
    RouteOpenAI --> RouteOpenRouter: OpenAI API error
    RouteOpenRouter --> CloudExecution_OR: OpenRouter online
    CloudExecution_OR --> LogSuccess: Return Output
    
    RouteOpenRouter --> FailState: All providers offline
    FailState --> [*]: Return System Error Message
    
    LogSuccess --> UpdateRoutingMetrics: Update latency/cost/throughput stats
    UpdateRoutingMetrics --> [*]
```

---

## 5. Main UI State Transitions

The JARVIS frontend Orb and VoiceWave widgets change state dynamically according to WebSocket status events:

1. **`idle`**: Default state. Central orb breathes slowly. Voice waves are flat. Wake word engine runs in background.
2. **`wake_word_detected`**: Triggered by local OpenWakeWord. Plays wake audio chime and pulses orb.
3. **`listening`**: Mic is active. Orb spins slowly; waveform displays active real-time input amplitude.
4. **`processing`**: LLM router is executing or Planner is building tasks. Orb glows intensely and rotates quickly; waveform displays computing loading pulses.
5. **`executing`**: Subagents are executing automation tools or shell commands. Orb transitions to an orange/amber color layout, spinning and pulsing; UI lists running task checkmarks.
6. **`speaking`**: TTS audio plays. Orb scales dynamically (core vibrates) in sync with audio amplitude levels.

---

## 6. Hand Gesture Control Flow

The local hand gesture processing pipelines map frames to 3D matrix manipulations:

```mermaid
sequenceDiagram
    participant Cam as Webcam Hardware
    participant HT as HandTracker (MediaPipe)
    participant OS as OrbScene (Three.js WebGL)
    participant UI as React UI HUD
    
    HT->>Cam: Request webcam stream (640x480)
    Cam->>HT: Stream video frames (transient memory)
    Note over HT: For each frame: run HandLandmarker.<br/>Detect wrist, thumb tip, index tip, middle MCP landmarks.
    HT->>HT: Calculate distance ratio between thumb & index tips
    alt Single Hand Pinch (Pinch Ratio less than 0.32)
        HT->>OS: Trigger rotateBy(dx, dy)
        OS->>OS: Rotate OrbitControls camera view
        HT->>UI: Emit state "hands: 1, mode: spin"
    else Double Hand Pinch
        HT->>OS: Trigger zoomBy(factor)
        OS->>OS: Change camera distance (zoom)
        HT->>UI: Emit state "hands: 2, mode: zoom"
    end
    HT->>UI: Render landmark connecting lines in mirrored overlay canvas
```
