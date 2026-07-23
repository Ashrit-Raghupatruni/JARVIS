# 🎨 Design System & Visual Guidelines

JARVIS features a futuristic sci-fi Heads-Up Display (HUD) interface inspired by Iron Man's home terminal. The interface prioritizes deep, dark space blues, semi-transparent glassmorphic panels, neon cyan glowing states, and a dedicated **Android Mobile Companion** Material 3 dark aesthetic. **Last Updated:** July 22, 2026

---

## 1. Color Palette

The theme values are configured globally in [index.css](file:///c:/Users/ashri/JARVIS/frontend/src/renderer/src/index.css) and mirrored in the Android companion app ([`mobile_app/src/screens/`](file:///c:/Users/ashri/JARVIS/mobile_app/src/screens/)):

### 1.1. Core Colors
* **Core Background (`--color-jarvis-bg`)**: `#070b13` — Deep space black-blue.
* **Alternative Background (`--color-jarvis-bg-alt`)**: `#0a1120` — Slightly lighter navy for panel separation.
* **Surface (`--color-jarvis-surface`)**: `rgba(10, 20, 38, 0.7)` — Glassmorphic background with alpha opacity.
* **Solid Surface (`--color-jarvis-surface-solid`)**: `#0c162b` — Non-translucent panel backing.
* **Hover Surface (`--color-jarvis-surface-hover`)**: `rgba(15, 30, 56, 0.95)` — Highlight backing for interactive items.

### 1.2. Accent & Neon Indicators
* **Primary Accent (`--color-jarvis-accent`)**: `#00e5ff` — High-intensity neon cyan (used for active states, lines, and primary button text).
* **Secondary Accent (`--color-jarvis-accent-2`)**: `#00aeff` — Electric blue (used for secondary status rings and badges).
* **Warning Accent (`--color-jarvis-accent-3`)**: `#ffaa00` — Neon orange/yellow (used for execution and security warning logs).
* **Glow Dim (`--color-jarvis-accent-dim`)**: `rgba(0, 229, 255, 0.15)` — Faded neon halo backing.
* **Glow Bright (`--color-jarvis-accent-glow`)**: `rgba(0, 229, 255, 0.35)` — Mid-intensity glow.
* **Success Indicator (`--color-jarvis-success`)**: `#00e676` — Neon green.
* **Danger/Error Indicator (`--color-jarvis-danger`)**: `#ff3d00` — Vivid neon red-orange.

---

## 2. Desktop Responsive Window Modes

1. **Fullscreen / Maximized Mode**:
   - Displays full OS Command Center dashboard (TitleBar, Command Dock, 3D Arc Reactor, ChatPanel, TaskProgress timeline, Visual Workflow Studio, Task Queue, Telemetry, and Automation cards).
2. **Resized / Compact Floating HUD Mode**:
   - Automatically activates when window is unmaximized or resized (`width < 900px` or `height < 600px`).
   - Auto-hides panels and displays **ONLY the central 3D Orb** with a minimal draggable header and **EXPAND** toggle button.
3. **Battery-Saver WebGL Canvas**:
   - `visibilitychange` listener pauses WebGL rendering loops when window is hidden/minimized to save CPU and battery.

---

## 3. Dedicated Android Mobile Companion UI Design System

The Android companion application ([`mobile_app/`](file:///c:/Users/ashri/JARVIS/mobile_app/)) follows Material 3 dark guidelines:

* **Theme**: `#050811` background, `#0e1726` surface cards, `#00e5ff` cyan accents.
* **Security Gatekeeper Modal**: High-contrast orange/red borders with 1-click `[ ✅ APPROVE ]`, `[ ❌ DENY ]`, `[ 🛡️ ALWAYS ALLOW ]`, and `[ ⛔ ALWAYS DENY ]` touch targets.
* **Real-time Telemetry HUD**: Material 3 stat cards for CPU %, RAM %, GPU %, battery status, and active desktop tasks.
