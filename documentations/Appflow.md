# 🔄 Application Flow & Execution Sequences

This document maps out the operational lifecycles, message-passing flows, state machines, and visual navigation interactions within the JARVIS personal AI OS ecosystem. **Last Updated:** August 8, 2026

---

## 1. Unified Navigation & Mode Switcher Flow

The top header bar consolidates all navigation into a single dropdown menu (`☰ Command Center ▾`), while the main hero visualizer panel automatically transitions between the **Idle Tech-Ring Circular HUD** and the **3D Arc Reactor system** based on speech state or manual user lock.

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

---

## 5. Master Unified Decision, Actuation, Verification & Learning Lifecycle Flow

The complete closed-loop lifecycle connecting perception, decision, safety, execution, verification, and learning:

```mermaid
sequenceDiagram
    participant User as User (Voice / Desktop / Mobile)
    participant Router as FastIntentRouter (0.0083ms)
    participant WorldModel as WorldModel (2.86ms State Refresh)
    participant Decision as Prash Neural Engine / Cloud LLM Router
    participant Safety as SafetyGatekeeper (Policy Interlock)
    participant Tools as ToolRegistry (56 Audited Tools)
    participant Verifier as ActionExecutionVerifier (27ms)
    participant Strategy as StrategyMemoryService (Learning)
    participant TTS as LocalTTSProvider (213ms SAPI)

    User->>Router: Natural language request or spoken voice command
    alt Deterministic Match
        Router-->>Decision: Fast-Path Intent (0A - 0H2)
    else Complex / Unseen Query
        Router->>WorldModel: Query active application, window title & cursor pos
        WorldModel-->>Decision: Inject real-time desktop state & personal memory facts
        Decision->>Decision: Synthesize tool call + parameters
    end

    Decision->>Safety: evaluate_tool_call(tool_name, parameters)
    alt Action Prohibited / High Risk Unconfirmed
        Safety-->>User: Intercept action, block execution, request confirmation
    else Action Allowed
        Safety-->>Tools: Dispatched tool execution
        Tools->>Tools: Execute Win32 UIA / Chromium accessibility / System API
        Tools->>Verifier: execute_and_verify(tool_name, args)
        Verifier->>Verifier: Observe post-condition desktop state delta (psutil & win32gui)
        Verifier->>Strategy: record_task_strategy_outcome(tool_name, success)
        Strategy-->>Decision: Update procedural confidence weights
        Verifier-->>TTS: Stream response text
        TTS-->>User: Local native SAPI speech synthesis (<250ms latency)
    end
```

---

## 6. Asynchronous Multimodal Generation & Specialized Domain Flow (Added September 8, 2026)

```mermaid
sequenceDiagram
    participant User as User / Client
    participant API as FastAPI /routes_ui
    participant Queue as AsyncGenerationJobManager
    participant SQLite as data/generation_jobs.db
    participant Worker as Background Async Task
    participant Adapter as Fail-Closed Media Adapter
    participant Skill as Multimodal / Science / Developer Skill

    User->>API: POST /api/ui/generation/jobs (or tool call generate_image_asset)
    API->>Queue: enqueue_job(media_type, prompt, params)
    Queue->>SQLite: INSERT INTO generation_jobs (job_id, status='queued', progress=0.0)
    Queue->>Worker: asyncio.create_task(_process_job())
    API-->>User: {status: "queued", job_id: "gen_uuid_..."}

    loop Background Generation Worker
        Worker->>Adapter: Preflight Check (API Keys / Torch GPU / Binary Availability)
        alt Preflight Failed (No Mock Simulation)
            Adapter-->>Worker: Raise ResourceUnavailableError
            Worker->>SQLite: UPDATE generation_jobs SET status='failed', error=msg
        else Preflight Succeeded
            Worker->>Adapter: Execute Real Synthesis
            Worker->>SQLite: UPDATE generation_jobs SET progress=0.5
            Adapter-->>Worker: Artifact Saved (e.g. data/artifacts/image_*.png)
            Worker->>SQLite: UPDATE generation_jobs SET status='completed', file_path=..., progress=1.0
        end
    end

    User->>API: GET /api/ui/generation/status/{job_id}
    API->>Queue: get_job_status(job_id)
    Queue->>SQLite: SELECT * FROM generation_jobs WHERE job_id=?
    SQLite-->>Queue: Record row
    Queue-->>API: {job_id, status, progress, file_path, error}
    API-->>User: JSON Status Response
```


