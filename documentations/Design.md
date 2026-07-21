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

## 5. Unified Single-Page AI OS Command Center Dashboard

The workspace layout is structured as a **single-page 3-column AI Command Center** with a top docked Control Header and a collapsible Settings Drawer:

1. **Top Docked Control Header**:
   - TitleBar frameless drag region with live status badges (`ONLINE`, provider latency).
   - View Filter Pills (`Unified View`, `Chat Focus`, `Telemetry`).
   - Docked Quick Action Buttons: Command Palette (`Ctrl+K`), System Benchmarks, Local ZIP Backup, Clear Chat, and Settings Drawer toggle.
2. **Left Wing (Interactive AI Operations)**:
   - **AI Chat & Voice Workspace** ([ChatPanel.tsx](file:///c:/Users/ashri/JARVIS/frontend/src/renderer/src/components/ChatPanel.tsx)): Multi-turn prompt execution with code blocks and tool call feedback.
   - **Computer Use & Screen Inspector** ([ComputerUseCard.tsx](file:///c:/Users/ashri/JARVIS/frontend/src/renderer/src/components/ComputerUseCard.tsx)): Displays physical display resolution, foreground focused window (`HWND`), and accessibility control tree count.
   - **Browser Automation & Research** ([BrowserAutomationCard.tsx](file:///c:/Users/ashri/JARVIS/frontend/src/renderer/src/components/BrowserAutomationCard.tsx)): Active Playwright browser profiles, tab navigator, and web search citation previews.
   - **Workflow & Macro Manager** ([WorkflowManagerCard.tsx](file:///c:/Users/ashri/JARVIS/frontend/src/renderer/src/components/WorkflowManagerCard.tsx)): Recorded macro workflows, instant playback buttons, and routine automation recorder.
3. **Center Hero Engine (Arc Reactor Core)**:
   - Houses the 3D WebGL Arc Reactor Orb ([Orb.tsx](file:///c:/Users/ashri/JARVIS/frontend/src/renderer/src/components/Orb.tsx)), dynamic audio waveform visualizer ([VoiceWave.tsx](file:///c:/Users/ashri/JARVIS/frontend/src/renderer/src/components/VoiceWave.tsx)), live STT speech transcript ([TranscriptView.tsx](file:///c:/Users/ashri/JARVIS/frontend/src/renderer/src/components/TranscriptView.tsx)), and voice state pills.
4. **Right Wing (Observability & Intelligence)**:
   - **Multi-Agent Orchestrator** ([AgentOrchestratorCard.tsx](file:///c:/Users/ashri/JARVIS/frontend/src/renderer/src/components/AgentOrchestratorCard.tsx)): Real-time status cards for CEO Agent, Planner Agent, Vision Agent, Coding Agent, and Research Agent.
   - **Running Tasks & Execution Timeline** ([TaskProgress.tsx](file:///c:/Users/ashri/JARVIS/frontend/src/renderer/src/components/TaskProgress.tsx)): Step-by-step progress bars and execution timelines.
   - **Memory Overview & Knowledge Graph** ([MemoryGraphCard.tsx](file:///c:/Users/ashri/JARVIS/frontend/src/renderer/src/components/MemoryGraphCard.tsx)): 6-scope memory metrics (Working, Conversational, Vector DB, Knowledge Graph nodes/edges).
   - **Knowledge Hub (RAG Service)** ([KnowledgeHubCard.tsx](file:///c:/Users/ashri/JARVIS/frontend/src/renderer/src/components/KnowledgeHubCard.tsx)): RAG document indexer (PDF, DOCX, PPTX), document uploader, and vector search preview.
5. **Bottom Hardware & Telemetry Deck**:
   - **System Telemetry Gauges** ([HardwareGauges.tsx](file:///c:/Users/ashri/JARVIS/frontend/src/renderer/src/components/HardwareGauges.tsx)): Real-time CPU %, RAM GB, GPU VRAM GB, and Network latency gauges.
   - **Connected LLM Providers** ([LLMProvidersCard.tsx](file:///c:/Users/ashri/JARVIS/frontend/src/renderer/src/components/LLMProvidersCard.tsx)): Live status cards for Groq (Llama 3.3 70B), Ollama (`qwen2.5-coder:3b`), Gemini, OpenRouter, and OpenAI.
   - **MCP Servers & Tool Registry** ([MCPServersCard.tsx](file:///c:/Users/ashri/JARVIS/frontend/src/renderer/src/components/MCPServersCard.tsx)): FastMCP skill tools count, active MCP subprocess servers, and risk scores.
   - **Command History Stream** ([CommandHistory.tsx](file:///c:/Users/ashri/JARVIS/frontend/src/renderer/src/components/CommandHistory.tsx)): Past command history stream.
