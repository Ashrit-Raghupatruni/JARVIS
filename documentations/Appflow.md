# 🔄 Application Flow & Execution Sequences

This document maps out the operational lifecycles, message-passing flows, state machines, and visual navigation interactions within the JARVIS personal AI OS ecosystem. **Last Updated:** July 31, 2026

---

## 1. Unified Navigation & Mode Switcher Flow

The top header bar consolidates all navigation into a single dropdown menu (`☰ Command Center ▾`), while the main hero visualizer panel automatically transitions between the **Idle Tech-Ring Circular HUD** and the **`facecap.glb` 3D Talking Face Avatar** based on speech state or manual user lock.

```mermaid
flowchart TD
    A[Electron Main Window Launch] --> B[Zustand App Store Init]
    B --> C[Top Header Bar: ☰ Command Center Dropdown]
    
    C -->|Select Option| D{Dropdown Selection}
    D -->|Command Center| E[Resizable 70/30 Hero Visualizer + Chat Panel]
    D -->|Agent Studio| F[Autonomous Agent Studio Dashboard]
    D -->|Chat History| G[Session Conversation Message Log]
    D -->|Workflow Studio| H[Visual Drag-and-Drop Workflow Builder]
    D -->|Task Queue| I[Task Queue Manager & Scheduler]
    D -->|Telemetry| J[Hardware Gauges & LLM Providers]
    D -->|Live Mode| K[Live Vision Perception & WebCam Stream]
    D -->|Automation| L[Computer Use & Playwright Browser]
    D -->|Debug Inspector| M[Live Debug Log & System Telemetry]
    
    E --> N{Visual Mode Switcher}
    N -->|AUTO DISPLAY| O[Idle HUD in Standby -> 3D Talking Face during TTS Speech]
    N -->|HUD LOCK| P[Lock Display to Idle Tech-Ring HUD]
    N -->|3D FACE LOCK| Q[Lock Display to Real facecap.glb 3D Talking Face Avatar]

    Q --> R[3D ROTATION TOGGLE: ON / OFF Button]
    R -->|ON| S[Smooth 360-Degree Continuous Y-Axis Rotation]
    R -->|OFF| T[Freeze Rotation in Position while blendShape1 Viseme Lip-Sync Continues]
```

---

## 2. Real `facecap.glb` 3D Face Engine Rendering & Viseme Speech Flow

```mermaid
sequenceDiagram
    participant User as User / TTS Service
    participant WebAudio as Web Audio API AnalyserNode
    participant Store as Zustand App Store
    participant Loader as GltfHeadLoader (GLTFLoader + MeshoptDecoder)
    participant FaceEngine as FaceRenderer (60 FPS WebGL)
    participant LipSync as VisemeLipSync Controller
    participant IdleAnim as NaturalIdleAnimator
    participant WebGL as Three.js Canvas (#00ff66 Green Hacker Theme)

    Loader->>FaceEngine: Asynchronously load real facecap.glb 3D asset
    Note over Loader: Procedural createImmediateHead fallback<br/>is 100% DELETED from codebase.
    
    User->>WebAudio: Stream TTS Audio Buffer (Speech Active)
    WebAudio->>Store: Update audioLevel (0.0 to 1.0) & set assistantState='speaking'
    Store->>FaceEngine: Render loop frame update (dt, elapsed)
    
    FaceEngine->>LipSync: evaluateFromAudio(audioLevel)
    LipSync-->>FaceEngine: Viseme Weights (blendShape1.jawOpen, mouthFunnel, mouthPucker)
    FaceEngine->>FaceEngine: Apply viseme weights to facecap.glb morphTargetInfluences
    
    FaceEngine->>IdleAnim: update(dt, elapsed, rootGroup, headMesh, is3DRotationEnabled)
    Note over IdleAnim: Evaluates chest/neck breathing sway,<br/>blendShape1.eyeBlink_L / eyeBlink_R blinking, and 360° Y rotation
    
    FaceEngine->>WebGL: Render green hacker PBR material (#00ff66, emissive #003311)
```

---

## 3. Autonomous Agent Ecosystem & IPC Execution Flow

```mermaid
sequenceDiagram
    participant User as User / AutonomousAgentStudio
    participant Ecosystem as AgentEcosystemService
    participant SubAgent as SubAgentInstance (Task Thread)
    participant Planner as PlannerAgent (LLM Tool Loop)
    participant Security as SecurityAgent / SafetyService
    participant SQLite as LongHorizonCheckpointService (SQLite WAL)
    participant Pruner as KVCachePruner

    User->>Ecosystem: spawn_subagent("CodeAgent", "Refactor API endpoints")
    Ecosystem->>SubAgent: Create isolated task thread
    SubAgent->>SQLite: create_goal() -> Initialize goal in data/jarvis.db
    
    SubAgent->>Security: IPC Audit Request ("Requesting permission to write file")
    Security->>Security: Execute SafetyService.validate_command()
    Security-->>SubAgent: IPC Audit Response ("Security audit APPROVED")
    
    SubAgent->>Planner: plan_and_execute(task_goal)
    loop Every Planner Step Yield
        Planner-->>Pruner: evaluate_and_prune(history)
        Pruner-->>Planner: Compressed history (saves >24% token budget)
        Planner-->>SubAgent: Yield Step Progress Update
        SubAgent->>SQLite: create_checkpoint() -> Save step state to agent_checkpoints
        SubAgent->>User: Broadcast WebSocket telemetry update
    end
    
    SubAgent->>SQLite: set_goal_status("completed")
```

---

## 4. Fail-Closed Mobile Companion Security Authentication Flow

```mermaid
flowchart TD
    A[Mobile Request to /api/v1/mobile/*] --> B{Check Authorization Header}
    B -->|Missing or Empty| C[Reject with 401 Unauthorized]
    B -->|Bearer Token Provided| D{Inspect Token Format}
    
    D -->|DEV_TOKEN_ Prefix| E{settings.DEBUG == True?}
    E -->|False| F[Log Warning & Reject 401 Unauthorized]
    E -->|True| G[Authenticate as Dev Device]
    
    D -->|JWT String| H[Execute jwt.decode with HS256 secret]
    H -->|Decode Failure / Expired / Tampered| I[Log Warning & Return None -> Reject 401 Unauthorized]
    H -->|Valid JWT & Registered Device| J[Authenticate Device Payload & Update last_active]
```
