# 🔄 Application Flow & Execution Sequences

This document maps out the operational lifecycles, message-passing flows, state machines, and mobile companion interactions within the JARVIS personal AI OS ecosystem. **Last Updated:** July 23, 2026

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

## 2. Dedicated Android Mobile Companion Pairing & Gatekeeper Flow

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

---

## 3. Mobile Security Approval Gatekeeper Intercept Flow

```mermaid
sequenceDiagram
    participant Planner as PlannerAgent (Desktop)
    participant Gate as MobileGatewayService
    participant Phone as Android Mission Control (Tab 3)
    participant User as User (Phone)
    
    Planner->>Planner: Detects dangerous action (delete file, terminal, shutdown)
    Planner->>Gate: request_approval(action_type, description)
    Note over Planner: Execution pauses (asyncio.Event locked)
    Gate->>Phone: Stream WS approval event / FCM push
    Phone->>User: Display Security Gatekeeper Modal (Approve, Deny, Always Allow)
    User->>Phone: Taps [ ✅ APPROVE ] or [ 🛡️ ALWAYS ALLOW ]
    Phone->>Gate: POST /api/v1/mobile/approvals/respond {approval_id, decision}
    Gate->>Planner: Unlocks asyncio.Event with 'approve' decision
    Planner->>Planner: Resumes tool execution safely
```

---

## 4. Native Windows UI Automation (UIA) Execution Flow

```mermaid
sequenceDiagram
    participant User as User (Voice / Chat)
    participant Planner as PlannerAgent
    participant UIA as UIAEngine (Win32 Accessibility)
    participant Win as Windows Desktop Application
    
    User->>Planner: "Click Save button in Notepad"
    Planner->>UIA: click_element_by_name("Save")
    UIA->>Win: Inspect Win32 control hierarchy (HWND & accessibility trees)
    UIA->>UIA: Match element name & compute exact bounding box
    UIA->>Win: Send native Win32 click message / pyautogui click
    UIA-->>Planner: Return {"status": "clicked", "target": "Save"}
    Planner-->>User: "Save button clicked, sir."
```

---

## 5. Self-Improving Action Trace, Reflection & Fault Recovery Sequence

```mermaid
sequenceDiagram
    participant User as User / Mobile Client
    participant Agent as PlannerAgent
    participant Exp as ExperienceEngineService
    participant Heal as SelfHealingEngine
    participant Strat as StrategyMemoryService
    participant Refl as ReflectionEngineService
    participant Mem as HybridMemorySystem
    
    User->>Agent: "Launch VS Code and start local server"
    Agent->>Strat: get_preferred_strategy("ui_automation")
    Strat-->>Agent: Returns "win32_uia" (Confidence: 95%)
    
    Agent->>Agent: Execute tool action
    alt Action Fails (e.g. Executable Path Changed)
        Agent->>Heal: diagnose_and_recover(action, error, target)
        Heal->>Heal: Scan PATH & Program Files for target.exe
        Heal-->>Agent: Auto-recovered path & update learned_recoveries
    end
    
    Agent->>Exp: record_experience(goal, duration, result, success, confidence)
    Exp->>Exp: Save trace into experiences.db (SQLite WAL)
    
    Agent->>Refl: reflect_on_task(goal, result, success, duration)
    Refl->>Mem: Store episode reflection & strategy recommendation
    Refl-->>User: Return response & streaming progress updates
```
