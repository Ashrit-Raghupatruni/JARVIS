# 📜 Development Rules & Architectural Guidelines

This document outlines the coding standards, safety guards, asset-based 3D face rules, mobile approval gatekeepers, and architectural rules for maintaining the JARVIS personal AI OS. **Last Updated:** July 29, 2026

---

## 1. Core Directives & Operating Constraints

> [!IMPORTANT]
> **Personal AI OS Scope**: Designed exclusively for **1 Windows PC + 1 Dedicated Android Phone**. Do NOT add cloud multi-tenancy, enterprise SaaS wrappers, microservices, or complex distributed databases. Keep local-first, fast, and maintainable.

> [!CAUTION]
> **No Unrequested Git Push**: Never run `git push` unless explicitly ordered by the user. All code modifications, builds, and documentation updates MUST remain local.

---

## 2. 3D Face Graphics & Renderer Rules

1. **Strict Asset-Based 3D Modeling (Zero Procedural Primitives)**:
   - All 3D head face geometry MUST be loaded from pre-modeled `.glb` / `.gltf` / `.vrm` assets via Three.js `GLTFLoader`.
   - Never procedurally approximate human face anatomy using primitive box, sphere, cylinder, or extrude meshes (`BoxGeometry`, `SphereGeometry`).
2. **Synchronous Frame-0 Head Asset Mount**:
   - The 3D renderer MUST mount an immediate head model synchronously on frame 0 so the canvas is **100% non-blank** on initial mount.
3. **Viseme Speech Lip-Sync & ARKit Morph Target Mapping**:
   - Audio volume levels MUST drive standard speech visemes (`viseme_aa`, `viseme_E`, `viseme_O`, `jawOpen`) and ARKit blendshapes (`eyeBlinkLeft`, `eyeBlinkRight`).
4. **Interactive 3D Rotation Toggle**:
   - The renderer MUST respect `is3DRotationEnabled` state from Zustand `appStore`: continuous smooth 360° Y-axis rotation when ON, frozen in position when OFF.

---

## 3. Safety & Security Gatekeeper Rules

1. **Mobile Security Gatekeeper**:
   - Dangerous operations (file deletion, terminal commands, system shutdown/restart, registry edits, software installs) MUST pause execution and request mobile security approval via `MobileGatewayService`.
   - Gatekeeper decisions: `approve`, `deny`, `always_allow`, `always_deny`. Expiration: 30-second timeout auto-denies for safety.
2. **Strict Identity Enforcement**:
   - The AI must ALWAYS identify as **J.A.R.V.I.S.** created by Ashrit Raghupatruni. Under NO circumstances should it state it is Qwen, Alibaba Cloud, ChatGPT, OpenAI, Llama, or Claude.
3. **Content Safety Guardrails**:
   - Background topic monitoring must block financial, day-trading, cryptocurrency, and gambling topics at the code level.
4. **Database Concurrency Rules**:
   - All SQLite connections MUST enforce `PRAGMA journal_mode=WAL;` to eliminate database write lock contention across asynchronous background threads.

---

## 4. Backend & Frontend Coding Standards (Python & TypeScript)

* **Asynchronous Execution (`async`/`await`)**:
  - Use `async` definitions for all I/O-bound operations (REST API handlers, WebSockets, database calls, subprocesses).
* **Type Safety & Pydantic Validation**:
  - All mobile API requests, REST endpoints, and WebSocket frames MUST use Pydantic v2 schemas (`backend/models/mobile_schemas.py`).
* **Clean Design Token Usage**:
  - CSS variables defined in `@theme` in `index.css` (`--color-jarvis-accent`, `--color-jarvis-bg`) MUST be used across components instead of ad-hoc custom values.
