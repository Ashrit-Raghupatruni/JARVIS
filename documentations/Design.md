# 🎨 Design System & Visual Guidelines

JARVIS features a futuristic sci-fi Heads-Up Display (HUD) interface inspired by Iron Man's home terminal. The interface prioritizes deep, dark space blues, semi-transparent glassmorphic panels, and neon cyan/blue glowing states to provide visual feedback for voice interactions.

---

## 1. Color Palette

The theme values are configured globally in [index.css](file:///c:/Users/ashri/JARVIS/frontend/src/renderer/src/index.css) using Tailwind CSS variables:

### 1.1. Core Colors
* **Core Background (`--color-jarvis-bg`)**: `#070b13` — Deep space black-blue.
* **Alternative Background (`--color-jarvis-bg-alt`)**: `#0a1120` — Slightly lighter navy for panel separation.
* **Surface (`--color-jarvis-surface`)**: `rgba(10, 20, 38, 0.7)` — Glassmorphic background with alpha opacity.
* **Solid Surface (`--color-jarvis-surface-solid`)**: `#0c162b` — Non-translucent panel backing.
* **Hover Surface (`--color-jarvis-surface-hover`)**: `rgba(15, 30, 56, 0.95)` — Highlight backing for interactive items.

### 1.2. Accent & Neon Indicators
* **Primary Accent (`--color-jarvis-accent`)**: `#00e5ff` — High-intensity neon cyan (used for active states, lines, and primary button text).
* **Secondary Accent (`--color-jarvis-accent-2`)**: `#00aeff` — Electric blue (used for secondary status rings and badges).
* **Warning Accent (`--color-jarvis-accent-3`)**: `#ffaa00` — Neon orange/yellow (used for execution and warning logs).
* **Glow Dim (`--color-jarvis-accent-dim`)**: `rgba(0, 229, 255, 0.15)` — Faded neon halo backing.
* **Glow Bright (`--color-jarvis-accent-glow`)**: `rgba(0, 229, 255, 0.35)` — Mid-intensity glow.
* **Success Indicator (`--color-jarvis-success`)**: `#00e676` — Neon green.
* **Danger/Error Indicator (`--color-jarvis-danger`)**: `#ff3d00` — Vivid neon red-orange.
* **Special Accent (`--color-jarvis-purple`)**: `#d500f9` — High-voltage purple.

### 1.3. Typography Colors
* **Primary Text (`--color-jarvis-text`)**: `#e1f5fe` — Ultra-light cyan-white (highly readable against deep backgrounds).
* **Dimmed Text (`--color-jarvis-text-dim`)**: `#b0bec5` — Cool silver grey.
* **Muted Text (`--color-jarvis-text-muted`)**: `#78909c` — Faded steel blue.

---

## 2. Typography & Font Pairings

* **Primary Sans-Serif Font**: `'Inter'`, `-apple-system`, `BlinkMacSystemFont`, `'Segoe UI'`, sans-serif.
  * Used for headings, body copy, settings options, and status bars.
  * Import weights: `300` (Light), `400` (Regular), `500` (Medium), `600` (Semi-bold), `700` (Bold).
* **Monospace Font**: `'JetBrains Mono'`, `'Fira Code'`, `'Cascadia Code'`, monospace.
  * Used for chat code snippets, terminal commands, execution logs, and step tracking metrics.

---

## 3. Glassmorphism & Depth System

JARVIS utilizes Backdrop Filters to create visual layering:

* **`.glass`**:
  * Background: `rgba(10, 20, 38, 0.6)`
  * Blur: `backdrop-filter: blur(16px)`
  * Border: `1px solid rgba(0, 229, 255, 0.1)`
* **`.glass-heavy`**:
  * Background: `rgba(7, 11, 19, 0.85)`
  * Blur: `backdrop-filter: blur(24px)`
  * Border: `1px solid rgba(0, 229, 255, 0.15)`
* **`.glass-light`**:
  * Background: `rgba(10, 20, 38, 0.4)`
  * Blur: `backdrop-filter: blur(12px)`
  * Border: `1px solid rgba(0, 229, 255, 0.08)`

---

## 4. Key Micro-Animations & Glow Effects

Animations are critical to represent JARVIS's cognitive load and listening states.

### 4.1. Central 3D JARVIS Arc Reactor & Shaders
* **3D Geometries**:
  * **Concentric Rings**: Outermost gear-notched circle with ticking LED lights, segmented mid-ring with endcap connectors, and inner alignment rings.
  * **Copper Coils**: 10 copper coils represented as 3D box wireframes placed radially, pulsing outwards.
  * **Central Core**: Spoke star connector, inner ring, and enshrouded volumetric glow bulbs.
  * **Drifting Text**: 1000+ tiny monospace strings ("sys.init()", "0x00E5FF") scattered in orbits.
  * **Debris Satellites**: 150+ tiny revolving meshes (icosahedrons, tetrahedrons) orbiting with trailing tails.
  * **Ambient Dust**: 1000+ points-based stardust particles drifting in the background.
  * **Scan Rings**: Faint rings sweeping vertically up/down, scaling dynamically to represent radar sweeps.
* **Dynamic Color Themes**:
  * **Neon Cyan/Blue Theme**: Cool tone for normal operations (Idle, Listening, Processing, Speaking).
  * **Neon Orange/Amber Theme**: Warm tone representing heavy computations and direct command execution.
* **Micro-Animations**:
  * **Concentric Counter-Rotation**: Outer, middle, and inner rings rotate in opposite directions to showcase 3D depth.
  * **Coil & Core Pulse**: Radial scale expansions of copper coils and glow bulbs matching the voice amplitude in real-time.
  * **Node Flickering**: Periodic random flicker cycles blitting check-node visibility.
  * **Chromatic Aberration Pass**: Custom fragment shader providing RGB fringe offsets and a subtle flicker.
* **Overlay Filters**:
  * Film Grain (0.05 opacity) + Horizontal Scanlines (0.2 opacity) + Vignette radial mask (0.7 opacity).

### 4.2. Glow Utilities
* **`.text-glow`**: Applies a CSS text-shadow using primary accent cyan (`#00e5ff`) with three layers of opacity.
* **`.box-glow`**: Applies a CSS box-shadow glow boundary to circular buttons or active indicator bars.

---

## 5. Main Screen Sections

The workspace layout is structured as a non-scrollable, responsive desktop overlay split into:

1. **TitleBar**:
   - Frameless drag handle area.
   - Display system logo, title, and standard Windows minimize/close widgets.
2. **StatusBar**:
   - Located at the bottom boundary.
   - Renders performance stats (current provider latency in milliseconds, token speed, memory status, active connections, and database status).
3. **Orb Panel (Central Siri Widget)**:
   - Houses the interactive central Orb.
   - Houses the `VoiceWave` component which draws a canvas/SVG sine wave that grows/flattens based on voice input audio stream volumes.
4. **Sliding Chat Panel**:
   - Sidebar panel containing the message log.
   - Handles file drop overlays, message list scroll locks, and thinking blocks.
5. **Task Progress Overlay**:
   - Renders multi-step agent plans (`AgentStep`) with animated checkbox states and latency timers for each sub-action.
