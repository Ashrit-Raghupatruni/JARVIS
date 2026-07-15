# 📜 Development Rules & Architectural Guidelines

This document outlines the coding standards, safety guards, and style patterns required when extending or maintaining the JARVIS codebase.

---

## 1. Safety & Execution Guardrails

> [!CAUTION]
> Safety is paramount. Desktop agents have direct access to the user's files and processes. All dangerous operations must be protected by explicit checkpoints.

* **Destructive Action Confirmation**:
  * Any script or agent tool that deletes, replaces, or overrides files/directories must present a confirmation request modal to the frontend before proceeding.
  * System modifications (e.g., editing environmental variables, killing critical system processes, shutting down the computer) must be blocked or prompt for user approval.
* **Command Validation**:
  * All CLI commands executed via `/api/command` or subagents must pass through the `SafetyService` keyword blacklist (e.g. blocking `rm -rf /`, `format C:`, etc.).
  * Input fields must be sanitized to prevent shell injection or parameter tampering.
* **Camera Access Guard**:
  * Webcam permissions must be handled gracefully. Video tracks must be explicitly stopped (`track.stop()`) and the camera stream resource set to null immediately when hand tracking is toggled off or when components unmount, ensuring the physical webcam indicator LED turns off.

---

## 2. Backend Coding Standards (Python)

* **Asynchronous Execution (`async`/`await`)**:
  * Use async definitions for all IO-bound operations (database queries, network requests, file reading, subprocess spawns).
  * Use `SQLAlchemy` async session calls and `aiosqlite` for database calls. Do not write synchronous database blocks.
* **Type Hinting**:
  * Explicit type signatures are required for all public functions, API route parameters, and database model columns.
  * Define schema envelopes in `schemas.py` using `Pydantic v2` models.
* **Exception Handling**:
  * Do not use bare `except:` blocks. Always catch specific exceptions (e.g., `TimeoutError`, `sqlite3.Error`).
  * Log warnings and errors via `Loguru` utilizing context bindings: `logger.error("Failed to execute tool: {}", err)`.
* **LLM Calls & Fallbacks**:
  * Always implement failover logic for cloud API requests. If a provider fails, catch the error and dispatch the query to the next fallback client in the provider list.

---

## 3. Frontend Coding Standards (Electron & React)

* **Tailwind Variables Usage**:
  * Never use hardcoded hex colors for theme-related items. Always reference custom theme variables defined in `index.css` (e.g., use `text-jarvis-accent` or `bg-jarvis-surface`).
* **Frameless Window Etiquette**:
  * Ensure the custom titlebar component maintains drag accessibility: include `-webkit-app-region: drag` for movement zones and `-webkit-app-region: no-drag` for buttons and links.
* **Zustand State Management**:
  * Centralize visual component states (microphone active, speech volume, active panel views) in global stores. Do not pass deep prop drills down the React tree.
* **Type Safety (TypeScript)**:
  * Define strict interface bindings for all WebSocket payload objects. Check the `type` discriminator before unpacking messages.
* **WebGL Memory Management**:
  * All Three.js objects (geometries, materials, textures, renderers) must be explicitly disposed of during React component unmount lifecycle hooks (`useEffect` return callbacks) to prevent system-level GPU memory leaks.

---

## 4. UI/UX Rules

* **Futuristic Glow Aesthetics**:
  * Keep visual components consistent with the sci-fi HUD theme. Use glassmorphism filters, glowing text/shadow layers, and smooth CSS transitions.
* **Micro-Animations**:
  * Make sure the central Orb component state corresponds exactly to the WebSocket connection status.
  * Never block UI interactions during long agent task executions. Ensure the chat panel remains interactive, and the task list displays clear, non-blocking checkmark progressions.
