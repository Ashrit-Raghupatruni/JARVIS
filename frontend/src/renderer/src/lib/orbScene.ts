import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "three/addons/postprocessing/UnrealBloomPass.js";
import { ShaderPass } from "three/addons/postprocessing/ShaderPass.js";

export interface OrbSceneApi {
  /** Rotate the camera around the orb by the given angles (radians). */
  rotateBy(deltaTheta: number, deltaPhi: number): void;
  /** Multiply the camera distance by `factor` (<1 zooms in, >1 zooms out). */
  zoomBy(factor: number): void;
  zoomIn(): void;
  zoomOut(): void;
  resetView(): void;
  /** Dynamic state updater. */
  setAssistantState(state: string, audioLevel: number): void;
  dispose(): void;
}

const HOME_POSITION = new THREE.Vector3(0, 0.5, 5.5);
const MIN_DISTANCE = 0.6;
const MAX_DISTANCE = 40;

// Dynamic themes definition (JARVIS theme color mappings)
const THEMES = {
  cyan: {
    bright: 0x00e5ff, // Neon Cyan
    mid: 0x00aeff,    // Neon Blue
    dim: 0x0055aa,    // Dark Blue
    faint: 0x002244,  // Very Dark Blue
    hot: 0x99f5ff,    // Light Cyan/White
  },
  orange: {
    bright: 0xffaa00, // Neon Orange
    mid: 0xff7700,    // Orange
    dim: 0xaa4400,    // Dark Orange
    faint: 0x441100,  // Deep Red/Orange
    hot: 0xffd580,    // Light Orange/White
  },
};

function createArcReactor(
  currentTheme: typeof THEMES.cyan,
  brightMats: any[],
  midMats: any[],
  dimMats: any[],
  faintMats: any[],
  hotMats: any[]
): THREE.Group {
  const group = new THREE.Group();

  function lineMat(color: number, opacity = 1, list = midMats) {
    const mat = new THREE.LineBasicMaterial({
      color,
      transparent: true,
      opacity,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    list.push({ material: mat });
    return mat;
  }

  // Helper to make a ring segment
  function makeArc(radius: number, startAngle: number, endAngle: number, segs = 30) {
    const pts: THREE.Vector3[] = [];
    for (let i = 0; i <= segs; i++) {
      const a = startAngle + (i / segs) * (endAngle - startAngle);
      pts.push(new THREE.Vector3(radius * Math.cos(a), radius * Math.sin(a), 0));
    }
    return new THREE.BufferGeometry().setFromPoints(pts);
  }

  // 1. OUTERMOST GEAR RING
  const outerRingGroup = new THREE.Group();
  const R_OUT = 2.15;
  
  // Continuous thin ring
  const circleGeo = new THREE.RingGeometry(R_OUT - 0.02, R_OUT, 80);
  const circleLine = new THREE.LineLoop(circleGeo, lineMat(currentTheme.dim, 0.4, dimMats));
  outerRingGroup.add(circleLine);

  // Outer teeth / notches (80 ticks)
  const teethPts: THREE.Vector3[] = [];
  for (let i = 0; i < 80; i++) {
    const a = (i / 80) * Math.PI * 2;
    const len = i % 10 === 0 ? 0.12 : i % 5 === 0 ? 0.08 : 0.04;
    teethPts.push(new THREE.Vector3(R_OUT * Math.cos(a), R_OUT * Math.sin(a), 0));
    teethPts.push(new THREE.Vector3((R_OUT + len) * Math.cos(a), (R_OUT + len) * Math.sin(a), 0));
  }
  const teethGeo = new THREE.BufferGeometry().setFromPoints(teethPts);
  const teeth = new THREE.LineSegments(teethGeo, lineMat(currentTheme.mid, 0.4, midMats));
  outerRingGroup.add(teeth);

  // Add dots along the outer ring (ticking LEDs)
  const dotCount = 12;
  const dotsPts: THREE.Vector3[] = [];
  for (let i = 0; i < dotCount; i++) {
    const a = (i / dotCount) * Math.PI * 2;
    dotsPts.push(new THREE.Vector3((R_OUT - 0.06) * Math.cos(a), (R_OUT - 0.06) * Math.sin(a), 0));
  }
  const dotsGeo = new THREE.BufferGeometry().setFromPoints(dotsPts);
  const dotsMat = new THREE.PointsMaterial({
    color: currentTheme.bright,
    size: 0.04,
    transparent: true,
    opacity: 0.75,
    blending: THREE.AdditiveBlending,
  });
  brightMats.push({ material: dotsMat });
  const dots = new THREE.Points(dotsGeo, dotsMat);
  outerRingGroup.add(dots);

  group.add(outerRingGroup);

  // 2. SEGMENTED STEP RING
  const segmentedRingGroup = new THREE.Group();
  const R_SEG = 1.85;
  const segCount = 6;
  const segAngle = (Math.PI * 2) / segCount;
  const segGap = 0.12; // radians gap

  for (let i = 0; i < segCount; i++) {
    const start = i * segAngle + segGap;
    const end = (i + 1) * segAngle - segGap;
    
    // Outer arc
    segmentedRingGroup.add(new THREE.Line(makeArc(R_SEG, start, end), lineMat(currentTheme.bright, 0.8, brightMats)));
    // Inner arc
    segmentedRingGroup.add(new THREE.Line(makeArc(R_SEG - 0.08, start, end), lineMat(currentTheme.mid, 0.5, midMats)));
    
    // Endcap connectors
    const capPts = [
      new THREE.Vector3((R_SEG - 0.08) * Math.cos(start), (R_SEG - 0.08) * Math.sin(start), 0),
      new THREE.Vector3(R_SEG * Math.cos(start), R_SEG * Math.sin(start), 0),
      new THREE.Vector3((R_SEG - 0.08) * Math.cos(end), (R_SEG - 0.08) * Math.sin(end), 0),
      new THREE.Vector3(R_SEG * Math.cos(end), R_SEG * Math.sin(end), 0)
    ];
    const capGeo = new THREE.BufferGeometry().setFromPoints(capPts);
    segmentedRingGroup.add(new THREE.LineSegments(capGeo, lineMat(currentTheme.dim, 0.45, dimMats)));
  }

  // Draw some numeric/tech details (additional circles and ticks inside)
  const innerRingGeo = new THREE.RingGeometry(R_SEG - 0.16, R_SEG - 0.12, 32);
  segmentedRingGroup.add(new THREE.Line(innerRingGeo, lineMat(currentTheme.faint, 0.25, faintMats)));

  group.add(segmentedRingGroup);

  // 3. COPPER COILS RING (The 10 classic Arc Reactor nodes!)
  const coilsGroup = new THREE.Group();
  const R_COIL = 1.48;
  const coilCount = 10;
  const coilAngle = (Math.PI * 2) / coilCount;
  
  const coilMeshes: THREE.LineSegments[] = [];

  for (let i = 0; i < coilCount; i++) {
    const angle = i * coilAngle;
    const coilCenter = new THREE.Vector3(R_COIL * Math.cos(angle), R_COIL * Math.sin(angle), 0);
    
    // Create a 3D box wireframe representing the copper coil winding
    const w = 0.22;
    const h = 0.18;
    const d = 0.14;
    const coilGeo = new THREE.BoxGeometry(w, h, d, 2, 2, 1);
    const coilEdges = new THREE.EdgesGeometry(coilGeo);
    const coilLine = new THREE.LineSegments(coilEdges, lineMat(currentTheme.bright, 0.9, brightMats));
    
    // Position and rotate to align radially
    coilLine.position.copy(coilCenter);
    coilLine.rotation.z = angle + Math.PI / 2;
    coilsGroup.add(coilLine);
    coilMeshes.push(coilLine);

    // Mini radial connectors under each coil
    const connPts = [
      new THREE.Vector3((R_COIL - 0.15) * Math.cos(angle), (R_COIL - 0.15) * Math.sin(angle), 0),
      new THREE.Vector3((R_COIL - 0.32) * Math.cos(angle), (R_COIL - 0.32) * Math.sin(angle), 0)
    ];
    const connGeo = new THREE.BufferGeometry().setFromPoints(connPts);
    coilsGroup.add(new THREE.Line(connGeo, lineMat(currentTheme.dim, 0.45, dimMats)));
  }

  // Thin ring backing the coils
  const coilsBackingGeo = new THREE.RingGeometry(R_COIL - 0.05, R_COIL + 0.05, 48);
  const coilsBacking = new THREE.LineLoop(coilsBackingGeo, lineMat(currentTheme.faint, 0.2, faintMats));
  coilsGroup.add(coilsBacking);

  group.add(coilsGroup);

  // 4. INNER ALIGNMENT RING WITH RADIAL GRIDS
  const innerGridGroup = new THREE.Group();
  const R_IN = 1.05;

  // Concentric backing rings
  innerGridGroup.add(new THREE.LineLoop(new THREE.RingGeometry(R_IN - 0.02, R_IN, 48), lineMat(currentTheme.dim, 0.4, dimMats)));
  innerGridGroup.add(new THREE.LineLoop(new THREE.RingGeometry(R_IN - 0.2, R_IN - 0.18, 48), lineMat(currentTheme.faint, 0.25, faintMats)));

  // Inner gear teeth (30 teeth pointing inwards)
  const innerTeethPts: THREE.Vector3[] = [];
  for (let i = 0; i < 30; i++) {
    const a = (i / 30) * Math.PI * 2;
    innerTeethPts.push(new THREE.Vector3(R_IN * Math.cos(a), R_IN * Math.sin(a), 0));
    innerTeethPts.push(new THREE.Vector3((R_IN - 0.06) * Math.cos(a), (R_IN - 0.06) * Math.sin(a), 0));
  }
  const innerTeethGeo = new THREE.BufferGeometry().setFromPoints(innerTeethPts);
  innerGridGroup.add(new THREE.LineSegments(innerTeethGeo, lineMat(currentTheme.mid, 0.5, midMats)));

  group.add(innerGridGroup);

  // 5. CENTRAL REACTOR CORE (Bulb / Glow sphere)
  const coreGroup = new THREE.Group();
  const R_CORE = 0.6;

  // Multi-spoke star connector
  const coreSpokesPts: THREE.Vector3[] = [];
  const spokeCount = 10;
  for (let i = 0; i < spokeCount; i++) {
    const a = (i / spokeCount) * Math.PI * 2;
    coreSpokesPts.push(new THREE.Vector3(0, 0, 0));
    coreSpokesPts.push(new THREE.Vector3((R_CORE - 0.05) * Math.cos(a), (R_CORE - 0.05) * Math.sin(a), 0));
  }
  const coreSpokesGeo = new THREE.BufferGeometry().setFromPoints(coreSpokesPts);
  coreGroup.add(new THREE.LineSegments(coreSpokesGeo, lineMat(currentTheme.bright, 0.7, brightMats)));

  // Inner ring
  const coreRingGeo = new THREE.RingGeometry(R_CORE - 0.06, R_CORE, 32);
  const coreRing = new THREE.LineLoop(coreRingGeo, lineMat(currentTheme.bright, 0.9, brightMats));
  coreGroup.add(coreRing);

  // Volumetric core glow mesh
  const coreGlowGeo = new THREE.SphereGeometry(R_CORE - 0.12, 16, 16);
  const coreGlowMat = new THREE.MeshBasicMaterial({
    color: currentTheme.hot,
    transparent: true,
    opacity: 0.22,
    blending: THREE.AdditiveBlending,
  });
  hotMats.push({ material: coreGlowMat });
  const coreGlowMesh = new THREE.Mesh(coreGlowGeo, coreGlowMat);
  coreGroup.add(coreGlowMesh);

  // Innermost tiny glow point
  const coreCenterGeo = new THREE.SphereGeometry(0.13, 8, 8);
  const coreCenterMat = new THREE.MeshBasicMaterial({
    color: currentTheme.hot,
    transparent: true,
    opacity: 0.9,
    blending: THREE.AdditiveBlending,
  });
  hotMats.push({ material: coreCenterMat });
  const coreCenterMesh = new THREE.Mesh(coreCenterGeo, coreCenterMat);
  coreGroup.add(coreCenterMesh);

  group.add(coreGroup);

  group.userData = {
    outerRingGroup,
    segmentedRingGroup,
    coilsGroup,
    coilMeshes,
    innerGridGroup,
    coreGroup,
    coreGlowMesh,
    coreGlowMat,
    coreCenterMesh,
    coreCenterMat
  };

  return group;
}

export function createOrbScene(container: HTMLElement): OrbSceneApi {
  const width = container.clientWidth;
  const height = container.clientHeight;

  // ——— SCENE ———
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(55, width / height, 0.1, 500);
  camera.position.copy(HOME_POSITION);

  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setSize(width, height);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 0.85;
  container.appendChild(renderer.domElement);

  // ——— POST PROCESSING ———
  const composer = new EffectComposer(renderer);
  composer.addPass(new RenderPass(scene, camera));

  const bloom = new UnrealBloomPass(
    new THREE.Vector2(width, height),
    1.6, // strength
    0.4, // radius
    0.2, // threshold
  );
  composer.addPass(bloom);

  // Chromatic aberration + color grade shader
  const chromaticShader = {
    uniforms: {
      tDiffuse: { value: null },
      uTime: { value: 0 },
      uIntensity: { value: 0.0035 },
      uColorShift: { value: new THREE.Vector3(1.0, 1.0, 1.0) }, // Dynamic color grade
    },
    vertexShader: `
      varying vec2 vUv;
      void main() {
        vUv = uv;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      }
    `,
    fragmentShader: `
      uniform sampler2D tDiffuse;
      uniform float uTime;
      uniform float uIntensity;
      uniform vec3 uColorShift;
      varying vec2 vUv;
      void main() {
        vec2 dir = vUv - vec2(0.5);
        float d = length(dir);
        float offset = uIntensity * d;
        float flicker = 1.0 + 0.02 * sin(uTime * 30.0) * sin(uTime * 7.3);
        vec4 cr = texture2D(tDiffuse, vUv + dir * offset);
        vec4 cg = texture2D(tDiffuse, vUv);
        vec4 cb = texture2D(tDiffuse, vUv - dir * offset * 0.5);
        gl_FragColor = vec4(cr.r, cg.g * 1.03, cb.b * 0.8, 1.0) * flicker;
        gl_FragColor.rgb = mix(gl_FragColor.rgb, gl_FragColor.rgb * uColorShift, 0.25);
      }
    `,
  };
  const chromaticPass = new ShaderPass(chromaticShader);
  composer.addPass(chromaticPass);

  // Controls
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.04;
  controls.minDistance = MIN_DISTANCE;
  controls.maxDistance = MAX_DISTANCE;
  controls.zoomSpeed = 1.4;
  controls.enablePan = false;

  // ——— MATERIAL COLLECTIONS FOR DYNAMIC THEMING ———
  const brightMats: THREE.ColorKey[] = [];
  const midMats: THREE.ColorKey[] = [];
  const dimMats: THREE.ColorKey[] = [];
  const faintMats: THREE.ColorKey[] = [];
  const hotMats: THREE.ColorKey[] = [];

  interface ColorKey {
    material: THREE.Material & { color?: THREE.Color };
  }

  function registerMat(material: THREE.Material, list: ColorKey[]) {
    if ("color" in material) {
      list.push({ material: material as THREE.Material & { color: THREE.Color } });
    }
    return material;
  }

  function lineMat(color: number, opacity = 1, list = midMats) {
    const mat = new THREE.LineBasicMaterial({
      color,
      transparent: true,
      opacity,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    registerMat(mat, list);
    return mat;
  }

  // ——— SCENE GROUP ———
  const orbGroup = new THREE.Group();
  scene.add(orbGroup);

  // ——— UTILITY RINGS CREATORS ———
  function latRing(radius: number, lat: number, segs = 120) {
    const r = radius * Math.cos(lat);
    const y = radius * Math.sin(lat);
    const pts: THREE.Vector3[] = [];
    for (let i = 0; i <= segs; i++) {
      const a = (i / segs) * Math.PI * 2;
      pts.push(new THREE.Vector3(r * Math.cos(a), y, r * Math.sin(a)));
    }
    return new THREE.BufferGeometry().setFromPoints(pts);
  }

  function meridian(radius: number, lon: number, segs = 120) {
    const pts: THREE.Vector3[] = [];
    for (let i = 0; i <= segs; i++) {
      const lat = (i / segs) * Math.PI - Math.PI / 2;
      pts.push(
        new THREE.Vector3(
          radius * Math.cos(lat) * Math.cos(lon),
          radius * Math.sin(lat),
          radius * Math.cos(lat) * Math.sin(lon),
        ),
      );
    }
    return new THREE.BufferGeometry().setFromPoints(pts);
  }

  // Current theme tracker
  let currentTheme = THEMES.cyan;
  let activeState = "idle";
  let stateSpeedMult = 1.0;
  let voiceScaleMult = 1.0;

  // ═══════════════════════════════════════════════
  // 3D HOLOGRAPHIC ARC REACTOR
  // ═══════════════════════════════════════════════
  const R1 = 2.0;
  const R3 = 0.9;

  const reactorGroup = createArcReactor(currentTheme, brightMats, midMats, dimMats, faintMats, hotMats);
  orbGroup.add(reactorGroup);

  // ═══════════════════════════════════════════════
  // CODE TEXT — dynamic colors
  // ═══════════════════════════════════════════════
  const codeSnippets = [
    "sys.init()", "0x00E5FF", "malloc()", ">> SCAN", "void*", "ACK",
    "SYNC OK", "ptr_ref", "exec()", "hash256", "::bind", "core.0",
    "01101001", "10110100", ">>> RDY", "HEAP 4K", "TCP/SYN",
    "mutex.lk", "IRQ 0x7", "DMA xfer", "REG EAX", "FAULT 0",
    "kernel.d", "pipe |>", "chmod +x", "fork()", "SIGTERM",
    "eth0: UP", "AES-256", "RSA 4096", "TLS 1.3", "HTTP/2",
    "latency", "200 OK", "PATCH /", "fn main", "use std",
    "impl Orb", "async {}", "spawn()", "arc::new", ".unwrap",
  ];

  interface SpriteDrift {
    phi: number;
    theta: number;
    r: number;
    speed: number;
  }

  function makeTextSprite(text: string, size = 0.08) {
    const c = document.createElement("canvas");
    c.width = 256;
    c.height = 32;
    const ctx = c.getContext("2d")!;
    ctx.font = "bold 14px Courier New";
    const alpha = 0.35 + Math.random() * 0.55;
    // Render in white so SpriteMaterial.color drives the exact color tone
    ctx.fillStyle = `rgba(255, 255, 255, ${alpha})`;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(text, 128, 16);
    const tex = new THREE.CanvasTexture(c);
    tex.minFilter = THREE.LinearFilter;
    const mat = new THREE.SpriteMaterial({
      map: tex,
      color: currentTheme.mid, // Use midMat color
      transparent: true,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    registerMat(mat, midMats);
    const s = new THREE.Sprite(mat);
    s.scale.set(size * 5, size * 0.7, 1);
    return s;
  }

  function scatterText(count: number, sizeFn: () => number, rFn: () => number, speedScale: [number, number]) {
    const group = new THREE.Group();
    for (let i = 0; i < count; i++) {
      const sp = makeTextSprite(
        codeSnippets[Math.floor(Math.random() * codeSnippets.length)],
        sizeFn(),
      );
      const phi = Math.acos(2 * Math.random() - 1);
      const theta = Math.random() * Math.PI * 2;
      const r = rFn();
      sp.position.set(
        r * Math.sin(phi) * Math.cos(theta),
        r * Math.cos(phi),
        r * Math.sin(phi) * Math.sin(theta),
      );
      sp.userData = {
        phi,
        theta,
        r,
        speed:
          (speedScale[0] + Math.random() * speedScale[1]) *
          (Math.random() > 0.5 ? 1 : -1),
      } satisfies SpriteDrift;
      group.add(sp);
    }
    return group;
  }

  const textOuter = scatterText(
    700, // Reduced slightly from 1200 for better performance in Electron
    () => 0.04 + Math.random() * 0.04,
    () => R1 + 0.03 + Math.random() * 0.08,
    [0.0002, 0.0008],
  );
  orbGroup.add(textOuter);

  const textInner = scatterText(
    80,
    () => 0.03 + Math.random() * 0.03,
    () => R3 + 0.02,
    [0.0005, 0.001],
  );
  orbGroup.add(textInner);

  const textAmbient = scatterText(
    250,
    () => 0.03,
    () => R3 + 0.2 + Math.random() * (R1 - R3 - 0.3),
    [0.0003, 0.0006],
  );
  orbGroup.add(textAmbient);

  // ═══════════════════════════════════════════════
  // ORBITING DEBRIS / SATELLITES
  // ═══════════════════════════════════════════════
  const debrisGeos = [
    new THREE.IcosahedronGeometry(0.012, 0),
    new THREE.IcosahedronGeometry(0.02, 0),
    new THREE.IcosahedronGeometry(0.03, 1),
    new THREE.IcosahedronGeometry(0.008, 0),
    new THREE.TetrahedronGeometry(0.015, 0),
    new THREE.OctahedronGeometry(0.018, 0),
  ];
  interface DebrisOrbit {
    orbitR: number;
    speed: number;
    tiltX: number;
    tiltZ: number;
    phase: number;
  }
  const debris: THREE.Mesh[] = [];
  for (let i = 0; i < 150; i++) { // Optimized count
    const geo = debrisGeos[Math.floor(Math.random() * debrisGeos.length)];
    const isBright = Math.random() > 0.7;
    const mat = new THREE.MeshBasicMaterial({
      color: isBright ? currentTheme.bright : currentTheme.mid,
      transparent: true,
      opacity: 0.3 + Math.random() * 0.6,
      blending: THREE.AdditiveBlending,
    });
    registerMat(mat, isBright ? brightMats : midMats);
    const mesh = new THREE.Mesh(geo, mat);
    const orbitR = 1.2 + Math.random() * 4.0;
    const speed = (0.08 + Math.random() * 0.6) * (Math.random() > 0.5 ? 1 : -1);
    const tiltX = (Math.random() - 0.5) * Math.PI * 0.9;
    const tiltZ = (Math.random() - 0.5) * Math.PI * 0.5;
    const phase = Math.random() * Math.PI * 2;
    mesh.userData = { orbitR, speed, tiltX, tiltZ, phase } satisfies DebrisOrbit;
    debris.push(mesh);
    orbGroup.add(mesh);

    if (Math.random() > 0.85) {
      const trailPts: THREE.Vector3[] = [];
      for (let j = 0; j <= 15; j++) {
        const a = -(j / 15) * 0.3;
        trailPts.push(
          new THREE.Vector3(
            orbitR * Math.cos(a + phase),
            orbitR * 0.08 * Math.sin(a * 3),
            orbitR * Math.sin(a + phase),
          ),
        );
      }
      const trail = new THREE.Line(
        new THREE.BufferGeometry().setFromPoints(trailPts),
        lineMat(currentTheme.faint, 0.08, faintMats),
      );
      mesh.add(trail);
    }
  }

  // ═══════════════════════════════════════════════
  // DUST PARTICLES
  // ═══════════════════════════════════════════════
  const dustCount = 1000; // Optimized
  const dustPos = new Float32Array(dustCount * 3);

  for (let i = 0; i < dustCount; i++) {
    const rr = 0.5 + Math.pow(Math.random(), 0.6) * 7;
    const theta = Math.random() * Math.PI * 2;
    const phi = Math.acos(2 * Math.random() - 1);
    dustPos[i * 3] = rr * Math.sin(phi) * Math.cos(theta);
    dustPos[i * 3 + 1] = rr * Math.cos(phi);
    dustPos[i * 3 + 2] = rr * Math.sin(phi) * Math.sin(theta);
  }

  const dustGeo = new THREE.BufferGeometry();
  dustGeo.setAttribute("position", new THREE.Float32BufferAttribute(dustPos, 3));

  const dotC = document.createElement("canvas");
  dotC.width = dotC.height = 64;
  const dCtx = dotC.getContext("2d")!;
  const g = dCtx.createRadialGradient(32, 32, 0, 32, 32, 32);
  g.addColorStop(0, "rgba(255,255,255,1)");
  g.addColorStop(0.2, "rgba(255,255,255,0.6)");
  g.addColorStop(0.5, "rgba(255,255,255,0.15)");
  g.addColorStop(1, "rgba(255,255,255,0)");
  dCtx.fillStyle = g;
  dCtx.fillRect(0, 0, 64, 64);

  const dustMat = new THREE.PointsMaterial({
    map: new THREE.CanvasTexture(dotC),
    size: 0.04,
    transparent: true,
    opacity: 0.5,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
    sizeAttenuation: true,
    color: currentTheme.bright,
  });
  registerMat(dustMat, brightMats);
  const dustPoints = new THREE.Points(dustGeo, dustMat);
  orbGroup.add(dustPoints);

  // ═══════════════════════════════════════════════
  // SCANNING RINGS
  // ═══════════════════════════════════════════════
  function makeScanRing(radius: number, thickness = 0.015) {
    const geo = new THREE.RingGeometry(radius - thickness, radius + thickness, 120);
    const mat = new THREE.MeshBasicMaterial({
      color: currentTheme.bright,
      transparent: true,
      opacity: 0,
      blending: THREE.AdditiveBlending,
      side: THREE.DoubleSide,
      depthWrite: false,
    });
    registerMat(mat, brightMats);
    const mesh = new THREE.Mesh(geo, mat);
    mesh.rotation.x = Math.PI / 2;
    return mesh;
  }

  const scanRing1 = makeScanRing(R1, 0.01);
  const scanRing2 = makeScanRing(R1 * 0.7, 0.008);
  orbGroup.add(scanRing1, scanRing2);

  // ═══════════════════════════════════════════════
  // HEXAGONAL NODES
  // ═══════════════════════════════════════════════
  const flickeringNodes: THREE.Object3D[] = [];
  for (let i = 0; i < 15; i++) {
    const phi = Math.acos(2 * Math.random() - 1);
    const theta = Math.random() * Math.PI * 2;
    const r = R1 + 0.02;
    const hexGeo = new THREE.CircleGeometry(0.03 + Math.random() * 0.02, 6);
    const hexEdges = new THREE.EdgesGeometry(hexGeo);
    const hex = new THREE.LineSegments(hexEdges, lineMat(currentTheme.mid, 0.5, midMats));
    hex.position.set(
      r * Math.sin(phi) * Math.cos(theta),
      r * Math.cos(phi),
      r * Math.sin(phi) * Math.sin(theta),
    );
    hex.lookAt(0, 0, 0);
    reactorGroup.add(hex);
    flickeringNodes.push(hex);
  }

  // ═══════════════════════════════════════════════
  // GESTURE CONTROL CAMERA SLOTS
  // ═══════════════════════════════════════════════
  const sphericalScratch = new THREE.Spherical();
  const offsetScratch = new THREE.Vector3();

  function rotateBy(deltaTheta: number, deltaPhi: number) {
    offsetScratch.copy(camera.position).sub(controls.target);
    sphericalScratch.setFromVector3(offsetScratch);
    sphericalScratch.theta -= deltaTheta;
    sphericalScratch.phi = THREE.MathUtils.clamp(
      sphericalScratch.phi - deltaPhi,
      0.05,
      Math.PI - 0.05,
    );
    sphericalScratch.makeSafe();
    offsetScratch.setFromSpherical(sphericalScratch);
    camera.position.copy(controls.target).add(offsetScratch);
    camera.lookAt(controls.target);
  }

  function zoomBy(factor: number) {
    offsetScratch.copy(camera.position).sub(controls.target);
    const dist = THREE.MathUtils.clamp(
      offsetScratch.length() * factor,
      MIN_DISTANCE,
      MAX_DISTANCE,
    );
    offsetScratch.setLength(dist);
    camera.position.copy(controls.target).add(offsetScratch);
  }

  function resetView() {
    camera.position.copy(HOME_POSITION);
    controls.target.set(0, 0, 0);
    camera.lookAt(controls.target);
    controls.update();
  }

  // ═══════════════════════════════════════════════
  // DYNAMIC STATE SYSTEM IMPLEMENTATION
  // ═══════════════════════════════════════════════
  function setAssistantState(state: string, audioLevel: number) {
    activeState = state;
    voiceScaleMult = audioLevel;

    // Determine target theme, speed multiplier and color shift
    let targetTheme = THEMES.cyan;
    let shiftVector = new THREE.Vector3(1.0, 1.0, 1.0);

    switch (state) {
      case "idle":
        stateSpeedMult = 0.8;
        targetTheme = THEMES.cyan;
        shiftVector.set(1.0, 1.05, 1.15); // Cooler cyan blue shift
        break;
      case "wake_word_detected":
        stateSpeedMult = 4.0;
        targetTheme = THEMES.cyan;
        shiftVector.set(1.2, 1.2, 1.2);
        break;
      case "listening":
        stateSpeedMult = 1.2 + audioLevel * 1.5;
        targetTheme = THEMES.cyan;
        shiftVector.set(1.0 + audioLevel * 0.3, 1.05 + audioLevel * 0.2, 1.15);
        break;
      case "processing":
        stateSpeedMult = 4.5;
        targetTheme = THEMES.cyan;
        shiftVector.set(1.15, 1.15, 1.25);
        break;
      case "speaking":
        stateSpeedMult = 1.0 + audioLevel * 2.0;
        targetTheme = THEMES.cyan;
        shiftVector.set(1.0, 1.05 + audioLevel * 0.15, 1.15);
        break;
      case "executing":
        stateSpeedMult = 2.5;
        targetTheme = THEMES.orange; // High intensity calculation theme
        shiftVector.set(1.2, 0.95, 0.7); // Amber/warm color shift
        break;
      default:
        stateSpeedMult = 1.0;
    }

    currentTheme = targetTheme;
    chromaticPass.uniforms.uColorShift.value.copy(shiftVector);

    // Apply colors to all registered materials
    brightMats.forEach((m) => m.material.color?.setHex(targetTheme.bright));
    midMats.forEach((m) => m.material.color?.setHex(targetTheme.mid));
    dimMats.forEach((m) => m.material.color?.setHex(targetTheme.dim));
    faintMats.forEach((m) => m.material.color?.setHex(targetTheme.faint));
    hotMats.forEach((m) => m.material.color?.setHex(targetTheme.hot));
  }

  // ═══════════════════════════════════════════════
  // ANIMATION LOOP
  // ═══════════════════════════════════════════════
  const clock = new THREE.Clock();
  let flickerTimer = 0;
  let rafId = 0;
  let disposed = false;

  function animate() {
    if (disposed) return;
    rafId = requestAnimationFrame(animate);
    const delta = clock.getDelta();
    const t = clock.getElapsedTime();

    const frameSpeed = delta * stateSpeedMult;

    // Apply rotations/movement to the Arc Reactor (tilted slightly towards camera)
    reactorGroup.rotation.x = 0.35 + Math.sin(t * 0.08) * 0.06; // tilted forward to show Z-depth of coils
    reactorGroup.rotation.y = Math.sin(t * 0.12) * 0.06;

    // Spin concentric rings in opposite directions
    reactorGroup.userData.outerRingGroup.rotation.z += frameSpeed * 0.09;
    reactorGroup.userData.segmentedRingGroup.rotation.z -= frameSpeed * 0.14;
    reactorGroup.userData.coilsGroup.rotation.z += frameSpeed * 0.04;
    reactorGroup.userData.innerGridGroup.rotation.z -= frameSpeed * 0.07;
    reactorGroup.userData.coreGroup.rotation.z += frameSpeed * 0.18;

    // Core pulsing calculation for Arc Reactor
    const wave3 = Math.pow(Math.max(0, Math.sin(t * 0.4)), 5);
    const surge = wave3 * 1.5;

    // Scale and opacity of Arc Reactor based on speech volume and state multipliers
    let audioAmp = 1.0;
    if (activeState === "listening" || activeState === "speaking") {
      audioAmp = 1.0 + voiceScaleMult * 0.45;
    }

    // Pulse the copper coils radially outwards
    const coilScale = 1.0 + Math.sin(t * 8.0) * 0.03 * stateSpeedMult + voiceScaleMult * 0.18;
    reactorGroup.userData.coilMeshes.forEach((mesh: THREE.LineSegments) => {
      mesh.scale.setScalar(coilScale);
    });

    // Pulse the core bulb and glow spheres
    const coreScale = (1.0 + surge * 0.4 + Math.sin(t * 5.0) * 0.06 * stateSpeedMult) * audioAmp;
    reactorGroup.userData.coreGroup.scale.setScalar(coreScale);

    const glowOpacity = Math.max(0.1, 0.2 + Math.sin(t * 6.0) * 0.08 + voiceScaleMult * 0.45);
    reactorGroup.userData.coreGlowMat.opacity = Math.min(0.85, glowOpacity);
    reactorGroup.userData.coreCenterMat.opacity = Math.min(1.0, 0.7 + voiceScaleMult * 0.3);

    // Satellites orbital position updates
    debris.forEach((d) => {
      const u = d.userData as DebrisOrbit;
      const a = t * u.speed * stateSpeedMult * 0.6 + u.phase;
      d.position.set(
        u.orbitR * Math.cos(a) * Math.cos(u.tiltX),
        u.orbitR * Math.sin(u.tiltX) * Math.sin(a * 0.8) + Math.sin(a * 0.3 + u.tiltZ) * 0.15,
        u.orbitR * Math.sin(a) * Math.cos(u.tiltZ),
      );
      d.rotation.x += 0.015;
      d.rotation.z += 0.01;
    });

    // Code text drift
    const driftGroups: [THREE.Group, number][] = [
      [textOuter, 1],
      [textInner, 2],
      [textAmbient, 1.2],
    ];
    for (const [group, mult] of driftGroups) {
      group.children.forEach((sp) => {
        const u = sp.userData as SpriteDrift;
        u.theta += u.speed * mult * (0.5 + stateSpeedMult * 0.5);
        sp.position.set(
          u.r * Math.sin(u.phi) * Math.cos(u.theta),
          u.r * Math.cos(u.phi),
          u.r * Math.sin(u.phi) * Math.sin(u.theta),
        );
      });
    }

    // Scan lines
    const scanY1 = Math.sin(t * 0.4) * R1;
    scanRing1.position.y = scanY1;
    const scanS1 = Math.sqrt(Math.max(0, R1 * R1 - scanY1 * scanY1)) / R1;
    scanRing1.scale.set(scanS1, scanS1, 1);
    (scanRing1.material as THREE.MeshBasicMaterial).opacity = 0.25 * scanS1;

    const scanY2 = Math.sin(t * 0.6 + 2) * R3;
    scanRing2.position.y = scanY2;
    const scanS2 = Math.sqrt(Math.max(0, R3 * R3 - scanY2 * scanY2)) / R3;
    scanRing2.scale.set(scanS2, scanS2, 1);
    (scanRing2.material as THREE.MeshBasicMaterial).opacity = 0.18 * scanS2;

    dustPoints.rotation.y += 0.0003 * stateSpeedMult;

    // Shader uniforms
    chromaticPass.uniforms.uTime.value = t;

    // Panel flickering
    flickerTimer += delta;
    if (flickerTimer > 0.08) {
      flickerTimer = 0;
      flickeringNodes.forEach((p) => {
        if (Math.random() > 0.94) {
          p.visible = !p.visible;
        }
      });
    }

    controls.update();
    composer.render();
  }

  animate();

  // Resize handler
  function onResize() {
    if (disposed) return;
    const w = container.clientWidth;
    const h = container.clientHeight;
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    renderer.setSize(w, h);
    composer.setSize(w, h);
  }
  window.addEventListener("resize", onResize);

  // Return API
  return {
    rotateBy,
    zoomBy,
    zoomIn() {
      zoomBy(0.8);
    },
    zoomOut() {
      zoomBy(1.25);
    },
    resetView,
    setAssistantState,
    dispose() {
      disposed = true;
      cancelAnimationFrame(rafId);
      window.removeEventListener("resize", onResize);
      controls.dispose();
      renderer.dispose();
      composer.dispose();
      try {
        container.removeChild(renderer.domElement);
      } catch {
        // Safe check
      }
    },
  };
}
