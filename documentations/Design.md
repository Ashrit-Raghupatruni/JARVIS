# 🎨 Design System & Visual Guidelines

JARVIS features an iconic sci-fi Heads-Up Display (HUD) interface inspired by Iron Man's home terminal. The interface prioritizes deep space navy backgrounds, semi-transparent glassmorphic panels, neon cyan glowing states, an asset-based 3D face visualizer, and a dedicated **Android Mobile Companion** Material 3 dark aesthetic. **Last Updated:** July 29, 2026

---

## 1. Color Palette & Typography

The theme values are configured globally in [index.css](file:///c:/Users/ashri/JARVIS/frontend/src/renderer/src/index.css) and mirrored in the Android companion app ([`mobile_app/src/screens/`](file:///c:/Users/ashri/JARVIS/mobile_app/src/screens/)):

### 1.1. Core Colors & Materials
* **Core Background (`--color-jarvis-bg`)**: `#070b13` — Deep space black-blue.
* **Alternative Background (`--color-jarvis-bg-alt`)**: `#0a1120` — Slightly lighter navy for panel separation.
* **Surface (`--color-jarvis-surface`)**: `rgba(10, 20, 38, 0.75)` — Glassmorphic background with alpha opacity.
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

### 1.3. Typography
* **Primary Font**: `Inter` (-apple-system, BlinkMacSystemFont, Segoe UI).
* **Monospace Font**: `JetBrains Mono` (used for code blocks, terminal outputs, and HUD badges).

---

## 2. 3D Face & HUD Visualizer Design Architecture

1. **Idle Circular Tech HUD (`IdleHUD.tsx` & `idleHudScene.ts`)**:
   - Digital HH:MM:SS clock with superscript seconds display.
   - J.A.R.V.I.S. wordmark with tagline (*"JUST A RATHER VERY INTELLIGENT SYSTEM"*).
   - Live date display and 80-notched rotating gear ring with ticking dot matrix LEDs.

2. **Asset-Based 3D Face Engine (`TalkingFace3D.tsx` & `FaceRenderer.ts`)**:
   - Pre-modeled 3D humanoid head asset loaded via `GLTFLoader`.
   - Metallic-roughness PBR skin shading with smooth organic cranium curves and sculpted 3D ears.
   - **3D ROTATION TOGGLE**: Interactive HUD button (`ROTATE: ON` / `ROTATE: OFF`) allowing users to freeze or resume continuous 360-degree rotation.
   - Real-time TTS audio amplitude viseme lip-sync and procedural double-blinking.

---

## 3. Resizable Panel Splitter & Header Dropdown Navigation

- **Header Command Dropdown (`☰ Command Center ▾`)**:
  - Consolidates 8 workspace sections into a single header dropdown button.
  - Includes **Chat History** session conversation log option.
- **70/30 Resizable Panel Splitter**:
  - Draggable vertical divider bar between the ~70% Left Visualizer Panel and ~30% Right Chat Panel.
  - `localStorage` split ratio persistence (`jarvis_split_ratio`).

---

## 4. Desktop Responsive Window Modes

1. **Fullscreen / Maximized Mode**:
   - Displays full OS Command Center dashboard (TitleBar, Command Dock, 3D Visualizer, ChatPanel, TaskProgress timeline, Visual Workflow Studio, Task Queue, Telemetry, and Automation cards).
2. **Resized / Compact Floating HUD Mode**:
   - Automatically activates when window is unmaximized or resized (`width < 900px` or `height < 600px`).
   - Auto-hides panels and displays **ONLY the central 3D Orb** with a minimal draggable header and **EXPAND** toggle button.
