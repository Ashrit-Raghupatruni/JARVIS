import {
  FilesetResolver,
  HandLandmarker,
  type NormalizedLandmark,
} from "@mediapipe/tasks-vision";

const WASM_CDN =
  "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.35/wasm";
const MODEL_URL =
  "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task";

// Landmark indices (MediaPipe hand model)
const WRIST = 0;
const THUMB_TIP = 4;
const INDEX_TIP = 8;
const INDEX_MCP = 5;
const MIDDLE_TIP = 12;
const MIDDLE_MCP = 9;
const RING_TIP = 16;
const RING_MCP = 13;
const PINKY_TIP = 20;
const PINKY_MCP = 17;

export interface HandTrackerConfigs {
  enabled: boolean;
  sensitivity: number; // 0.5 to 3.0
  smoothing: number; // 0.05 to 0.95 (lower = more smoothed/laggy)
  pinchThreshold: number; // multiplier of handScale
  scrollSpeed: number; // multiplier of scroll delta
  fps: number;
  cameraDevice?: string;
}

export interface TrackerTelemetry {
  hands: number;
  fps: number;
  activeGesture: string;
  confidence: number;
  handControlActive: boolean;
}

export interface HandTrackerCallbacks {
  /** Triggered when a cursor action needs to be executed on backend. */
  onHandAction(action: string, params: Record<string, any>): void;
  /** Telemetry status callback. */
  onTelemetry(telemetry: TrackerTelemetry): void;
}

export class HandTracker {
  private video: HTMLVideoElement;
  private overlay: HTMLCanvasElement;
  private callbacks: HandTrackerCallbacks;
  private landmarker: HandLandmarker | null = null;
  private stream: MediaStream | null = null;
  private rafId = 0;
  private running = false;
  private lastVideoTime = -1;

  // Smoothing states
  private smoothedX = 0.5;
  private smoothedY = 0.5;
  private trendX = 0;
  private trendY = 0;
  private initialized = false;

  // Pinch states
  private leftPinching = false;
  private rightPinching = false;
  private ringPinching = false; // Used for Volume
  private pinkyPinching = false; // Used for Escape
  
  // Drag states
  private isDragging = false;
  private dragStartX = 0;
  private dragStartY = 0;
  private dragActive = false;

  // Double click states
  private lastLeftPinchReleaseTime = 0;

  // Scroll states
  private lastScrollY = 0.5;
  private scrollActive = false;

  // Volume states
  private lastVolumeY = 0.5;

  // Throttling states for sub-millisecond cursor dispatch
  private lastMoveTime = 0;
  private lastSentX = -1;
  private lastSentY = -1;

  // Telemetry variables
  private frameCount = 0;
  private lastFpsTime = 0;
  private currentFps = 0;
  private activeGesture = "NONE";
  private confidence = 0;

  // Configs
  private configs: HandTrackerConfigs = {
    enabled: true,
    sensitivity: 1.6,
    smoothing: 0.45,
    pinchThreshold: 0.32,
    scrollSpeed: 40.0,
    fps: 30,
  };

  constructor(
    video: HTMLVideoElement,
    overlay: HTMLCanvasElement,
    callbacks: HandTrackerCallbacks,
  ) {
    this.video = video;
    this.overlay = overlay;
    this.callbacks = callbacks;
  }

  updateConfigs(newConfigs: Partial<HandTrackerConfigs>): void {
    this.configs = { ...this.configs, ...newConfigs };
    console.log("HandTracker configurations updated:", this.configs);
  }

  async start(): Promise<void> {
    if (this.running) return;

    const constraints: MediaStreamConstraints = {
      video: {
        width: 640,
        height: 480,
        facingMode: "user",
        frameRate: this.configs.fps,
        deviceId: this.configs.cameraDevice ? { exact: this.configs.cameraDevice } : undefined,
      },
      audio: false,
    };

    try {
      this.stream = await navigator.mediaDevices.getUserMedia(constraints);
    } catch (e) {
      console.warn("Could not start camera with devices constraints, falling back to default video source.", e);
      this.stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
    }

    this.video.srcObject = this.stream;
    await this.video.play();

    const fileset = await FilesetResolver.forVisionTasks(WASM_CDN);
    const options = {
      baseOptions: { modelAssetPath: MODEL_URL, delegate: "GPU" as const },
      runningMode: "VIDEO" as const,
      numHands: 1, // Only track primary hand for desktop cursor control
      minHandDetectionConfidence: 0.65,
      minHandPresenceConfidence: 0.65,
      minTrackingConfidence: 0.65,
    };

    try {
      this.landmarker = await HandLandmarker.createFromOptions(fileset, options);
    } catch {
      this.landmarker = await HandLandmarker.createFromOptions(fileset, {
        ...options,
        baseOptions: { ...options.baseOptions, delegate: "CPU" as const },
      });
    }

    this.running = true;
    this.lastFpsTime = performance.now();
    this.loop();
  }

  stop(): void {
    this.running = false;
    cancelAnimationFrame(this.rafId);
    this.landmarker?.close();
    this.landmarker = null;
    this.stream?.getTracks().forEach((t) => t.stop());
    this.stream = null;
    this.video.srcObject = null;
    this.initialized = false;
    this.leftPinching = false;
    this.rightPinching = false;
    this.isDragging = false;
    this.dragActive = false;
    this.scrollActive = false;
    const ctx = this.overlay.getContext("2d");
    ctx?.clearRect(0, 0, this.overlay.width, this.overlay.height);
    this.emitTelemetry(0, "OFFLINE", 0);
  }

  private loop = () => {
    if (!this.running) return;
    this.rafId = requestAnimationFrame(this.loop);

    if (!this.landmarker || this.video.readyState < 2) return;
    if (this.video.currentTime === this.lastVideoTime) return;
    this.lastVideoTime = this.video.currentTime;

    // Track FPS
    this.frameCount++;
    const now = performance.now();
    const elapsed = now - this.lastFpsTime;
    if (elapsed >= 1000) {
      this.currentFps = Math.round((this.frameCount * 1000) / elapsed);
      this.frameCount = 0;
      this.lastFpsTime = now;
    }

    const result = this.landmarker.detectForVideo(this.video, now);
    const score = result.handConfidence?.[0] ?? 0;
    this.confidence = Math.round(score * 100);

    if (result.landmarks && result.landmarks.length > 0) {
      this.processHand(result.landmarks[0]);
      this.drawOverlay(result.landmarks[0]);
    } else {
      this.activeGesture = "NONE";
      this.emitTelemetry(0, "NONE", 0);
      const ctx = this.overlay.getContext("2d");
      ctx?.clearRect(0, 0, this.overlay.width, this.overlay.height);
    }
  };

  private isFingerRaised(lm: any[], tipIdx: number, mcpIdx: number): boolean {
    // Y coordinate is inverted (0 is top, 1 is bottom)
    return lm[tipIdx].y < lm[mcpIdx].y;
  }

  private processHand(lm: any[]): void {
    const handScale = Math.hypot(lm[WRIST].x - lm[MIDDLE_MCP].x, lm[WRIST].y - lm[MIDDLE_MCP].y);
    if (handScale < 1e-6) return;

    // ── 1. Coordinates Resolution (Cursor pointer = Index finger tip)
    // Mirroring X coordinates so hand-right maps to screen-right
    const rawX = 1 - lm[INDEX_TIP].x;
    const rawY = lm[INDEX_TIP].y;

    // Apply sensitivity bounding box mapping (e.g. center box)
    const sens = this.configs.sensitivity;
    const sizeX = 1 / sens;
    const sizeY = 1 / sens;
    const minX = 0.5 - sizeX / 2;
    const minY = 0.5 - sizeY / 2;

    let targetX = (rawX - minX) / sizeX;
    let targetY = (rawY - minY) / sizeY;

    // Clamp values to [0, 1] bounds
    targetX = Math.max(0, Math.min(1, targetX));
    targetY = Math.max(0, Math.min(1, targetY));

    // Double exponential smoothing filter (Holt's Linear Trend)
    if (!this.initialized) {
      this.smoothedX = targetX;
      this.smoothedY = targetY;
      this.trendX = 0;
      this.trendY = 0;
      this.initialized = true;
    } else {
      const alpha = this.configs.smoothing; // default 0.45
      const beta = 0.25; // Trend smoothing parameter
      
      const prevX = this.smoothedX;
      const prevY = this.smoothedY;
      
      this.smoothedX = alpha * targetX + (1 - alpha) * (prevX + this.trendX);
      this.smoothedY = alpha * targetY + (1 - alpha) * (prevY + this.trendY);
      
      this.trendX = beta * (this.smoothedX - prevX) + (1 - beta) * this.trendX;
      this.trendY = beta * (this.smoothedY - prevY) + (1 - beta) * this.trendY;
    }

    const screenX = Math.round(this.smoothedX * window.screen.width);
    const screenY = Math.round(this.smoothedY * window.screen.height);

    // Send cursor movement if hand control is enabled (~60Hz max, >=2px delta)
    if (this.configs.enabled && !this.scrollActive && !this.ringPinching) {
      const now = performance.now();
      if (now - this.lastMoveTime >= 15 && (Math.abs(screenX - this.lastSentX) >= 2 || Math.abs(screenY - this.lastSentY) >= 2)) {
        this.callbacks.onHandAction("move", { x: screenX, y: screenY });
        this.lastMoveTime = now;
        this.lastSentX = screenX;
        this.lastSentY = screenY;
      }
    }

    // ── 2. Gesture Calculations
    // Pinch ratios
    const leftPinchRatio = Math.hypot(lm[THUMB_TIP].x - lm[INDEX_TIP].x, lm[THUMB_TIP].y - lm[INDEX_TIP].y) / handScale;
    const rightPinchRatio = Math.hypot(lm[THUMB_TIP].x - lm[MIDDLE_TIP].x, lm[THUMB_TIP].y - lm[MIDDLE_TIP].y) / handScale;
    const ringPinchRatio = Math.hypot(lm[THUMB_TIP].x - lm[RING_TIP].x, lm[THUMB_TIP].y - lm[RING_TIP].y) / handScale;
    const pinkyPinchRatio = Math.hypot(lm[THUMB_TIP].x - lm[PINKY_TIP].x, lm[THUMB_TIP].y - lm[PINKY_TIP].y) / handScale;

    const threshold = this.configs.pinchThreshold;
    const releaseThreshold = threshold + 0.12; // Hysteresis

    // Resolve Gesture State
    let currentGesture = "NONE";

    // ── LEFT PINCH: Left Click or Drag-and-Drop
    if (this.leftPinching && leftPinchRatio > releaseThreshold) {
      // Left pinch release
      this.leftPinching = false;
      const now = performance.now();
      const pinchDuration = now - this.lastLeftPinchReleaseTime;

      if (this.dragActive) {
        // Stop drag
        this.callbacks.onHandAction("click", { button: "left", action: "release" });
        this.dragActive = false;
      } else {
        // Execute Left Click
        if (pinchDuration < 450) {
          // Double Click
          this.callbacks.onHandAction("click", { button: "left", action: "double_click" });
          this.lastLeftPinchReleaseTime = 0; // Reset
        } else {
          // Single Click
          this.callbacks.onHandAction("click", { button: "left", action: "click" });
          this.lastLeftPinchReleaseTime = now;
        }
      }
    } else if (!this.leftPinching && leftPinchRatio < threshold && !this.rightPinching && !this.ringPinching && !this.pinkyPinching) {
      // Left pinch start
      this.leftPinching = true;
      this.dragStartX = screenX;
      this.dragStartY = screenY;
      // Start timeout or distance checks to decide click vs drag
    }

    if (this.leftPinching) {
      currentGesture = "LEFT PINCH";
      // Drag verification: if pinched and moved past accidental dragging threshold (25px)
      const dist = Math.hypot(screenX - this.dragStartX, screenY - this.dragStartY);
      if (dist > 25 && !this.dragActive) {
        this.dragActive = true;
        this.callbacks.onHandAction("click", { button: "left", action: "press" }); // Mouse down for dragging
      }
    }

    // ── RIGHT PINCH: Right Click
    if (this.rightPinching && rightPinchRatio > releaseThreshold) {
      this.rightPinching = false;
      this.callbacks.onHandAction("click", { button: "right", action: "click" });
    } else if (!this.rightPinching && rightPinchRatio < threshold && !this.leftPinching) {
      this.rightPinching = true;
    }

    if (this.rightPinching) {
      currentGesture = "RIGHT PINCH";
    }

    // ── ESCAPE: Thumb + Pinky pinch (Escape key)
    if (this.pinkyPinching && pinkyPinchRatio > releaseThreshold) {
      this.pinkyPinching = false;
      this.callbacks.onHandAction("key", { key: "escape" });
    } else if (!this.pinkyPinching && pinkyPinchRatio < threshold && !this.leftPinching && !this.rightPinching) {
      this.pinkyPinching = true;
    }

    if (this.pinkyPinching) {
      currentGesture = "ESCAPE GESTURE";
    }

    // ── VOLUME CONTROL: Thumb + Ring pinch (Volume control via vertical movement)
    if (this.ringPinching && ringPinchRatio > releaseThreshold) {
      this.ringPinching = false;
    } else if (!this.ringPinching && ringPinchRatio < threshold && !this.leftPinching && !this.rightPinching) {
      this.ringPinching = true;
      this.lastVolumeY = rawY;
    }

    if (this.ringPinching) {
      currentGesture = "VOLUME GESTURE";
      const dy = rawY - this.lastVolumeY;
      if (Math.abs(dy) > 0.08) {
        const action = dy < 0 ? "volume_up" : "volume_down"; // Inverted camera coordinates
        this.callbacks.onHandAction("key", { key: action });
        this.lastVolumeY = rawY; // Reset anchor
      }
    }

    // ── SCROLL GESTURE: Index & Middle raised, Ring & Pinky folded
    const indexRaised = this.isFingerRaised(lm, INDEX_TIP, INDEX_MCP);
    const middleRaised = this.isFingerRaised(lm, MIDDLE_TIP, MIDDLE_MCP);
    const ringFolded = !this.isFingerRaised(lm, RING_TIP, RING_MCP);
    const pinkyFolded = !this.isFingerRaised(lm, PINKY_TIP, PINKY_MCP);

    if (indexRaised && middleRaised && ringFolded && pinkyFolded && !this.leftPinching && !this.rightPinching && !this.ringPinching) {
      currentGesture = "SCROLL";
      if (!this.scrollActive) {
        this.scrollActive = true;
        this.lastScrollY = rawY;
      } else {
        const dy = rawY - this.lastScrollY;
        if (Math.abs(dy) > 0.04) {
          const direction = dy > 0 ? "down" : "up"; // Natural scroll mapping
          this.callbacks.onHandAction("scroll", {
            direction,
            amount: Math.max(1, Math.round(Math.abs(dy) * this.configs.scrollSpeed)),
          });
          this.lastScrollY = rawY;
        }
      }
    } else {
      this.scrollActive = false;
    }

    this.activeGesture = currentGesture;
    this.emitTelemetry(1, currentGesture, this.confidence);
  }

  private emitTelemetry(hands: number, gesture: string, confidence: number): void {
    this.callbacks.onTelemetry({
      hands,
      fps: this.currentFps,
      activeGesture: gesture,
      confidence,
      handControlActive: this.configs.enabled && this.running,
    });
  }

  private drawOverlay(lm: any[]): void {
    const ctx = this.overlay.getContext("2d");
    if (!ctx) return;
    const { width, height } = this.overlay;
    ctx.clearRect(0, 0, width, height);

    // Draw hand skeleton skeleton structure
    ctx.strokeStyle = this.leftPinching ? "#39ff14" : "rgba(0, 229, 255, 0.4)";
    ctx.lineWidth = 2;

    // Draw palm/finger connections
    const connections = [
      [WRIST, 1], [1, 2], [2, 3], [3, THUMB_TIP], // Thumb
      [WRIST, INDEX_MCP], [INDEX_MCP, 6], [6, 7], [7, INDEX_TIP], // Index
      [INDEX_MCP, MIDDLE_MCP], [MIDDLE_MCP, 10], [10, 11], [11, MIDDLE_TIP], // Middle
      [MIDDLE_MCP, RING_MCP], [RING_MCP, 14], [14, 15], [15, RING_TIP], // Ring
      [RING_MCP, PINKY_MCP], [PINKY_MCP, 18], [18, 19], [19, PINKY_TIP], // Pinky
      [WRIST, PINKY_MCP]
    ];

    for (const [start, end] of connections) {
      const sx = (1 - lm[start].x) * width;
      const sy = lm[start].y * height;
      const ex = (1 - lm[end].x) * width;
      const ey = lm[end].y * height;

      ctx.beginPath();
      ctx.moveTo(sx, sy);
      ctx.lineTo(ex, ey);
      ctx.stroke();
    }

    // Draw active pointer tip index indicator (green highlight)
    const indexX = (1 - lm[INDEX_TIP].x) * width;
    const indexY = lm[INDEX_TIP].y * height;
    ctx.fillStyle = "#39ff14";
    ctx.beginPath();
    ctx.arc(indexX, indexY, 6, 0, Math.PI * 2);
    ctx.fill();

    // Draw other joints
    ctx.fillStyle = "rgba(0, 229, 255, 0.8)";
    for (const joint of [WRIST, THUMB_TIP, MIDDLE_TIP, RING_TIP, PINKY_TIP]) {
      const jx = (1 - lm[joint].x) * width;
      const jy = lm[joint].y * height;
      ctx.beginPath();
      ctx.arc(jx, jy, 4, 0, Math.PI * 2);
      ctx.fill();
    }
  }
}
