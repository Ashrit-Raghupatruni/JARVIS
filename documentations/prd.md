# 🤖 Product Requirements Document (PRD) — JARVIS Personal AI Operating System

## 1. Executive Summary & Vision

JARVIS is a **Personal AI Operating System** designed for single-user deployment across **1 Windows Laptop (Brain) + 1 Dedicated Android Phone (Companion HUD)**. Inspired by Iron Man's home computer assistant, JARVIS acts as an autonomous digital companion bridging human speech with Windows OS operations, application control, and mobile remote monitoring. **Last Updated:** July 22, 2026

Unlike commercial cloud SaaS platforms, JARVIS is **100% local-first, privacy-focused, free of hosting fees**, and optimized for sub-millisecond local execution with dynamic cloud AI fallback when high reasoning capabilities are needed.

---

## 2. Target Device Topology & Core Specs

```
┌───────────────────────────────────────┐         ┌───────────────────────────────────────┐
│          PRIMARY WINDOWS LAPTOP       │         │        DEDICATED ANDROID PHONE        │
│ - FastAPI Monolith Engine (Port 8000) │◄───────►│ - Material 3 Mobile Companion App     │
│ - Electron Desktop Shell (3D Orb HUD) │   LAN   │ - Mobile Security Approval Gatekeeper │
│ - SQLite WAL + ChromaDB Knowledge Hub │   WS    │ - Remote Voice & Telemetry Dashboard  │
└───────────────────────────────────────┘         └───────────────────────────────────────┘
```

---

## 3. Key Product Requirements

### 3.1. Dedicated Android Companion App & Security Gatekeeper
* **One-Time Pairing**: 6-digit numeric PIN & QR code scanning (`/api/v1/mobile/pair`) issuing 1-year signed JWT access tokens saved to `data/trusted_devices.json`.
* **Mobile Security Approval System (Gatekeeper)**:
  - Dangerous actions (file deletions, terminal commands, system restarts, registry updates) pause desktop execution and send instant mobile notifications.
  - Interactive approval choices: `[ ✅ Approve ]`, `[ ❌ Deny ]`, `[ 🛡️ Always Allow ]`, `[ ⛔ Always Deny ]`, `[ ⏱️ Auto-Timeout (30s) ]`.
* **Real-time Hardware Telemetry HUD**: Material 3 live metric cards for CPU %, RAM %, GPU %, battery, active task, and AI provider.
* **Remote Desktop Commands**: 1-tap `Shutdown`, `Restart`, `Lock`, `Launch App`, `Pause AI`, `Cancel Task`.
* **On-Demand Screen Snapshot Preview**: Non-continuous privacy-first screen previews with touch annotation capabilities.

### 3.2. Native Windows UI Automation & File Search
* **Resolution-Independent UI Control**: Native Win32 Accessibility UI Automation (`UIAEngine`) for locating buttons and text fields by title, control type, or automation ID without pixel coordinate drift.
* **Sub-second Natural Language File Indexing**: SQLite FTS5 indexer (`FileIndexerService`) for searching local workspace documents and code.

### 3.3. Core Stability & Hardware Optimization
* **SQLite WAL Mode**: Enforced `PRAGMA journal_mode=WAL;` across all database connections to eliminate concurrent write lock errors.
* **WebGL Battery Saver**: `visibilitychange` listener in `Orb.tsx` pauses WebGL rendering loops when window is hidden or minimized.
* **Adaptive Windowing**: Fullscreen dashboard vs. compact floating 3D Orb HUD toggle.
