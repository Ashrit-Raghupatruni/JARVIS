# 🎨 Design System, Styling Tokens & Visual Architecture

This document defines the visual identity, styling tokens, glassmorphism UI components, Three.js 3D rendering pipeline, and green hacker aesthetic system for JARVIS. **Last Updated:** August 8, 2026

---

## 1. Green Hacker Design System (`#00ff66`)

The entire JARVIS frontend uses a sleek, high-contrast **Green Hacker Terminal Aesthetic** with dark emerald backgrounds, neon emerald accents, glassmorphic panels, and glowing Three.js PBR materials.

### Core Color Tokens (`index.css`)
- **Primary Accent**: `#00ff66` (Neon Green / Hacker Emerald)
- **Secondary Accent**: `#00cc55` (Subdued Emerald)
- **Deep Background**: `#050d08` (Dark Emerald Navy)
- **Glass Panel Surface**: `rgba(5, 13, 8, 0.85)` with `backdrop-filter: blur(12px)`
- **Border Overlay**: `rgba(0, 255, 102, 0.25)` with inner glow `0 0 15px rgba(0,255,102,0.15)`
- **Text Primary**: `#00ff66`
- **Text Muted**: `#00b347`

---

## 2. 3D Face Model Rendering Pipeline (`facecap.glb`)

### Asset Specification
- **Model File**: `facecap.glb` (332.8 KB) sourced from official Three.js dev examples (`mrdoob/three.js`). Located at `frontend/src/renderer/src/assets/models/head.glb` and `public/models/head.glb`.
- **Loader Engine**: [`GltfHeadLoader.ts`](file:///c:/Users/ashri/JARVIS/frontend/src/renderer/src/lib/face-engine/loaders/GltfHeadLoader.ts) using `three/examples/jsm/loaders/GLTFLoader.js` with `MeshoptDecoder` (`three/examples/jsm/libs/meshopt_decoder.module.js`).
- **Zero Procedural Fallbacks**: `createImmediateHead()` has been **100% DELETED** from the codebase.
- **PBR Material Styling**: Applied `MeshStandardMaterial` (`color: 0x00ff66`, `roughness: 0.25`, `metalness: 0.8`, `emissive: 0x003311`) to all head mesh geometries.

### Morph Target Viseme & Animation Mapping
- **Speech Lip-Sync**: Web Audio API `audioLevel` (0.0 to 1.0) maps to morph target `blendShape1.jawOpen` in [`VisemeLipSync.ts`](file:///c:/Users/ashri/JARVIS/frontend/src/renderer/src/lib/face-engine/animation/VisemeLipSync.ts).
- **Natural Eye Blinking**: Randomized double-blinking targets `blendShape1.eyeBlink_L` and `blendShape1.eyeBlink_R` in [`NaturalIdleAnimator.ts`](file:///c:/Users/ashri/JARVIS/frontend/src/renderer/src/lib/face-engine/animation/NaturalIdleAnimator.ts).
- **Smooth 360-Degree Continuous Y-Axis Rotation**: Managed by `NaturalIdleAnimator` when 3D Rotation Toggle is enabled.

---

## 3. Autonomous Agent Studio Dashboard UI

The `AutonomousAgentStudio.tsx` component is accessible under `☰ Command Center ▾` dropdown and provides a 4-quadrant layout:
1. **Sub-Agent Active Cards**: Displays role tags (`CodeAgent`, `ResearchAgent`, `SecurityAgent`), real-time progress bars, token counts, and current step descriptions.
2. **IPC Message Stream**: Live log of inter-agent IPC requests, security audit approvals, and CEO responses.
3. **Multi-Day Goal Checkpoints**: Timeline view of SQLite WAL goal states (`data/jarvis.db`) with step titles and progress tags.
4. **KV-Cache Token Pruning Meter**: Real-time context compression statistics showing token savings, compression ratios, and total prune events.

---

## 4. HUD Telemetry & Native System Lock Controls Design

### Native Lock & Security Control Tokens
- **Quick-Lock Action**: Dedicated hardware lock trigger invoking native Win32 `LockWorkStation` API via `/api/system/lock`.
- **Face Lock UI Indicator**: Visual lock state badges showing biometric verification confidence, camera worker FPS, and live enrollment status.
- **Multi-Monitor Coordinate Visualizer**: Responsive topology mapping of active monitors, primary display indicators, and coordinate bounds `(x, y, w, h)`.
- **System Diagnostics HUD**: Sub-second gauge indicators for Battery Charge %, AC Power Plugged state, CPU load, and RAM usage.
- **Fail-Closed Confirmation Modals**: High-contrast amber/red warning dialogs for destructive actions (`kill_process`, `delete_file`, `recover_hung_application`) requiring explicit biometric or manual authorization.

---

## 5. Multimodal Generation & Domain UI Extensions (Added September 8, 2026)

### UI Components & Dashboard Integration
- **`DeveloperDashboard.tsx` (`MULTIMODAL & NOTES` Subtab)**:
  - Real-time generation job status card displaying UUID, media type badges (`image`, `video`, `3d`), status badges (`queued`, `processing`, `completed`, `failed`), progress bars, output paths, and fail-closed error diagnostics.
  - Persistent Markdown notes explorer rendering notes from `data/notes/*.md` with titles, byte sizes, and markdown chips.
- **REST Endpoints & Visual Badges**:
  - `/api/ui/generation/status/{job_id}`: Sub-50ms JSON polling.
  - `/api/ui/generation/jobs`: Recent job timeline.
  - `/api/ui/notes`: Stored notes catalog.
- **Fail-Closed Warning Dialogs**:
  - Automatically highlights unconfigured API keys or hardware requirements (e.g. CUDA GPU for local Stable Diffusion / SVD) without presenting simulated completions.


