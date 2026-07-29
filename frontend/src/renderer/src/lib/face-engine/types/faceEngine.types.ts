/**
 * Production-Grade 3D Face Generation & Shader Engine Types
 * Architectural Standard: Pixar / Unreal Engine / Meta Reality Labs
 */

// ── 1. Facial Anatomy Parameters ──────────────────────────────────────────────
export interface FacialAnatomyConfig {
  skullProportions: {
    headWidth: number // 0.8 to 1.2
    headHeight: number // 0.8 to 1.2
    headDepth: number // 0.8 to 1.2
    jawWidth: number // 0.7 to 1.3
    chinProminence: number // 0.5 to 1.5
    cheekboneWidth: number // 0.8 to 1.3
    foreheadHeight: number // 0.8 to 1.2
  }
  eyeAnatomy: {
    interocularDistance: number // mm (e.g. 63mm default)
    eyeTiltDeg: number // degrees (-10 to +10)
    eyelidOpening: number // 0.0 (closed) to 1.0 (fully open)
    irisDiameterMm: number // mm (default ~12mm)
    pupilDiameterMm: number // mm (2mm to 8mm)
    corneaCurvature: number // index of refraction ~1.376
    scleraVascularity: number // 0.0 to 1.0
    tearLineMoisture: number // 0.0 to 1.0
  }
  noseAnatomy: {
    bridgeHeight: number
    bridgeWidth: number
    tipProtrusion: number
    nostrilWidth: number
  }
  mouthAnatomy: {
    lipWidth: number
    upperLipFullness: number
    lowerLipFullness: number
    philtrumDepth: number
    teethVisibility: number
  }
}

// ── 2. Skin System & Subsurface Scattering ─────────────────────────────────────
export interface SkinSystemConfig {
  ethnicity: string
  skinToneHex: string
  melaninIndex: number // 0.0 to 1.0
  hemoglobinIndex: number // 0.0 to 1.0 (blood flow)
  subsurfaceScattering: {
    enabled: boolean
    subsurfaceColor: string // Subsurface scatter tint (e.g. #ff3311 for blood)
    subsurfaceRadius: number // mm depth (e.g. 1.5mm to 3.0mm)
    scatteringPower: number
  }
  microDetails: {
    poreDensity: number // 0.0 to 1.0
    poreDepth: number
    microWrinkleIntensity: number
    freckleDensity: number
    pigmentationVariation: number
    oilinessRoughness: number // 0.05 (glossy) to 0.7 (matte)
  }
}

// ── 3. Hair System Config ──────────────────────────────────────────────────────
export interface HairSystemConfig {
  style: string
  colorHex: string
  melanin: number
  strandDensity: number
  hairlineOffset: number
  flyawayCount: number
  anisotropicSpecular: number
  facialHair: {
    type: 'none' | 'stubble' | 'beard' | 'mustache'
    density: number
    lengthMm: number
  }
}

// ── 4. Lighting & Camera Config ───────────────────────────────────────────────
export interface StudioLightingConfig {
  keyLight: {
    intensity: number
    colorTemperatureK: number // 3200K to 6500K
    angleDeg: number
    softness: number
  }
  fillLight: {
    intensity: number
    colorTemperatureK: number
    angleDeg: number
  }
  rimLight: {
    intensity: number
    colorHex: string
    angleDeg: number
  }
  environmentHdri: string
  acesTonemapping: boolean
  exposure: number
}

export interface PortraitCameraConfig {
  focalLengthMm: 50 | 85 | 105
  apertureFStop: number // e.g. 1.4, 1.8, 2.8, 4.0
  focusDistanceMeters: number
  sensorSizeMm: number // 36mm full frame
  iso: number
  shutterSpeed: string
  whiteBalanceK: number
}

// ── 5. FACS Facial Expressions ────────────────────────────────────────────────
export interface FacsExpressionConfig {
  neutral: number
  jawOpen: number // AU26 / AU27
  mouthWide: number // AU12 / AU20
  eyeBlinkLeft: number // AU45
  eyeBlinkRight: number // AU45
  browInnerUp: number // AU1
  browLowerer: number // AU4
  cheekRaiser: number // AU6
  noseWrinkler: number // AU9
  lipStretcher: number // AU20
}

// ── 6. Prompt Engine Parameters ───────────────────────────────────────────────
export interface PromptEngineInput {
  age: number
  gender: 'woman' | 'man' | 'non-binary' | 'character'
  ethnicity: string
  skinToneDescriptor: string
  hairStyle: string
  hairColor: string
  eyeColor: string
  expression: string
  cameraLens: '50mm' | '85mm' | '105mm'
  lightingPreset: 'three-point' | 'rembrandt' | 'golden-hour' | 'cinematic'
  accessories?: string[]
  environment?: string
  qualityPreset: 'photorealistic' | 'stylized-3d' | 'high-detail-scan'
}

export interface GeneratedPromptOutput {
  positivePrompt: string
  negativePrompt: string
  cfgScale: number
  samplingSteps: number
  sampler: string
  targetResolution: { width: number; height: number }
  seed: number
}

// ── 7. Quality Validation Report ──────────────────────────────────────────────
export interface QualityValidationReport {
  passed: boolean
  score: number // 0 to 100
  anomaliesDetected: string[]
  autoCorrectionsApplied: string[]
  metrics: {
    facialSymmetryScore: number
    skinTextureRealismScore: number
    lightingCoherenceScore: number
    eyeRealismScore: number
  }
}
