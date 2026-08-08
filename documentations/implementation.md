# 🏗️ Implementation Details & Architectural Specifications

This document outlines the concrete code modules, service integration patterns, virtual environment dependencies, and security implementations in JARVIS. **Last Updated:** August 8, 2026

---

## 1. Connected Security Sandbox & Code Executions

### Implementation Design ([`sandbox.py`](file:///c:/Users/ashri/JARVIS/backend/services/security/sandbox.py))
- Integrates `SecuritySandbox` for python and shell executions inside standard tools pipelines with zero bypass paths.
- Scrubs API keys and environment variables on subprocess initialization to block leakage.
- Enforces secrets masking inside `rbac.py` on tool outputs.
- Restricts tool permissions and locks reading/writing sensitive files (`.env`, `vault.bin`).

---

## 2. Autonomous Agent Ecosystem Services

### 1. `AgentEcosystemService` ([`backend/services/agent_ecosystem.py`](file:///c:/Users/ashri/JARVIS/backend/services/agent_ecosystem.py))
- Spawns specialized sub-agents (`SubAgentInstance`) executing real `PlannerAgent` loops.
- Manages the IPC message bus (`IPCMessage`) and routes security audit requests directly to `SafetyService.validate_command()`.

### 2. `SubAgentInstance` ([`backend/agents/subagent.py`](file:///c:/Users/ashri/JARVIS/backend/agents/subagent.py))
- Executes background tasks via `PlannerAgent.plan_and_execute()`.
- On every step yield, records progress to `LongHorizonCheckpointService` in SQLite WAL (`data/jarvis.db`) and broadcasts progress to WebSockets.

### 3. `LongHorizonCheckpointService` ([`backend/services/long_horizon_checkpoint.py`](file:///c:/Users/ashri/JARVIS/backend/services/long_horizon_checkpoint.py))
- Manages `goal_queue` and `agent_checkpoints` tables in SQLite WAL.
- Stores step titles, state dictionaries, timestamps, and goal status (`running`, `paused`, `completed`, `failed`).

### 4. `KVCachePruner` ([`backend/services/kv_cache_pruner.py`](file:///c:/Users/ashri/JARVIS/backend/services/kv_cache_pruner.py))
- Context window compression service evaluated inside `LLMService.generate_response()` ([`backend/services/llm.py`](file:///c:/Users/ashri/JARVIS/backend/services/llm.py)).
- Synthesizes old context turns when history exceeds token budget, saving >24% token space.

---

## 3. Fail-Closed Security Implementation

### 1. `MobileAuthService` ([`backend/services/mobile_auth.py`](file:///c:/Users/ashri/JARVIS/backend/services/mobile_auth.py))
- `verify_token()`: Decodes JWT with `HS256`. Returns `None` on any decode failure or corrupt token (fails closed with 401 Unauthorized).
- `DEV_TOKEN_`: Strictly gated behind `settings.DEBUG == True`. Rejected immediately in production mode.

### 2. `VoiceIntelligenceService` ([`backend/services/voice_intelligence.py`](file:///c:/Users/ashri/JARVIS/backend/services/voice_intelligence.py))
- `verify_speaker_biometrics()` / `verify_face_biometrics()`: Return `verified: False` with `confidence: 0.0` whenever reference embeddings are missing or uncalibrated.

### 3. `MobileGatewayService` & Router ([`backend/api/mobile_router.py`](file:///c:/Users/ashri/JARVIS/backend/api/mobile_router.py))
- `request_shutdown_approval`: Returns `approved: False` (`decision: deny`) if `gateway_svc` is unavailable.
