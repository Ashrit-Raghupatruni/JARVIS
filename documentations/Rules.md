# 📜 Development Rules & Architectural Standards

This document establishes the mandatory engineering rules, safety constraints, coding standards, and architectural directives for JARVIS. **Last Updated:** July 31, 2026

---

## 1. Safety & Security Directives (FAIL CLOSED)

1. **Fail-Closed Security Default**: Security endpoints and token verification MUST fail closed.
   - `mobile_auth.py` (`verify_token()`): On any JWT decode failure, expired token, or missing claim, MUST return `None` (401 Unauthorized). Zero default trusted identity fallbacks.
   - `DEV_TOKEN_` prefixes MUST be gated behind `settings.DEBUG == True`.
   - Security approvals and biometric verifications MUST return `verified: False` or `approved: False` when services or reference embeddings are missing.
2. **Sanitize Terminal Commands**: All shell commands MUST pass through `SafetyService.sanitize_command()` before execution.
3. **No Unconfirmed Destructive Actions**: Disk formatting, file deletion, registry modifications, or process termination require user approval.

---

## 2. 3D Rendering & Visual Asset Directives

1. **Strict Asset-Based 3D Geometry**:
   - DO NOT create face geometry using procedural primitive math (`BoxGeometry`, `SphereGeometry`, `CylinderGeometry`).
   - Use verified `facecap.glb` asset loaded via `GLTFLoader` with `MeshoptDecoder`.
   - `createImmediateHead()` is **100% DELETED** and forbidden from returning to the codebase.
2. **Green Hacker Aesthetic**:
   - Maintain `--color-jarvis-accent: #00ff66` and `--color-jarvis-bg: #050d08` across CSS tokens, Three.js PBR materials, and dashboard UI components.

---

## 3. Autonomous Agent Ecosystem Directives

1. **Real Sub-Agent Execution**:
   - Sub-agent instances (`SubAgentInstance`) MUST execute real `PlannerAgent` LLM tool loops.
   - DO NOT use mock timer loops (`asyncio.sleep(0.5)`) or canned log strings in production sub-agent runners.
2. **Persistent Goal Checkpointing**:
   - Step progress MUST be recorded to SQLite WAL (`data/jarvis.db`) via `LongHorizonCheckpointService`.
3. **Active KV-Cache Pruning**:
   - `LLMService` MUST evaluate `KVCachePruner.evaluate_and_prune()` on conversation history before calling LLM providers when token budget is exceeded.

---

## 4. Source Control & Archive Directives

1. **No GitHub Push Without Explicit Permission**:
   - NEVER run `git push origin feature` or push commits to remote repositories without explicit user instruction.
2. **Keep `jarvis.zip` Up-to-Date**:
   - Re-generate `jarvis.zip` incorporating modified code and `.glb` model assets locally.
