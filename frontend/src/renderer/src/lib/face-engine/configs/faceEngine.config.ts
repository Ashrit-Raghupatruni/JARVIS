import {
  FacialAnatomyConfig,
  SkinSystemConfig,
  HairSystemConfig,
  StudioLightingConfig,
  PortraitCameraConfig,
  FacsExpressionConfig
} from '../types/faceEngine.types'

export const DEFAULT_FACIAL_ANATOMY: FacialAnatomyConfig = {
  skullProportions: {
    headWidth: 1.0,
    headHeight: 1.0,
    headDepth: 1.0,
    jawWidth: 1.0,
    chinProminence: 1.0,
    cheekboneWidth: 1.0,
    foreheadHeight: 1.0
  },
  eyeAnatomy: {
    interocularDistance: 63, // mm
    eyeTiltDeg: 0,
    eyelidOpening: 0.85,
    irisDiameterMm: 12.0,
    pupilDiameterMm: 4.0,
    corneaCurvature: 1.376, // Human Cornea IOR
    scleraVascularity: 0.15,
    tearLineMoisture: 0.95
  },
  noseAnatomy: {
    bridgeHeight: 1.0,
    bridgeWidth: 1.0,
    tipProtrusion: 1.0,
    nostrilWidth: 1.0
  },
  mouthAnatomy: {
    lipWidth: 1.0,
    upperLipFullness: 1.0,
    lowerLipFullness: 1.0,
    philtrumDepth: 1.0,
    teethVisibility: 0.1
  }
}

export const DEFAULT_SKIN_SYSTEM: SkinSystemConfig = {
  ethnicity: 'Neutral',
  skinToneHex: '#e0ac69',
  melaninIndex: 0.35,
  hemoglobinIndex: 0.45,
  subsurfaceScattering: {
    enabled: true,
    subsurfaceColor: '#ff3a1a',
    subsurfaceRadius: 2.2, // mm
    scatteringPower: 1.4
  },
  microDetails: {
    poreDensity: 0.85,
    poreDepth: 0.6,
    microWrinkleIntensity: 0.4,
    freckleDensity: 0.15,
    pigmentationVariation: 0.2,
    oilinessRoughness: 0.25
  }
}

export const DEFAULT_HAIR_SYSTEM: HairSystemConfig = {
  style: 'Natural Straight',
  colorHex: '#1a110b',
  melanin: 0.85,
  strandDensity: 100000,
  hairlineOffset: 0.0,
  flyawayCount: 150,
  anisotropicSpecular: 0.8,
  facialHair: {
    type: 'none',
    density: 0,
    lengthMm: 0
  }
}

export const DEFAULT_STUDIO_LIGHTING: StudioLightingConfig = {
  keyLight: {
    intensity: 4.5,
    colorTemperatureK: 5600, // Daylight
    angleDeg: 45,
    softness: 0.8
  },
  fillLight: {
    intensity: 2.0,
    colorTemperatureK: 4800,
    angleDeg: -45
  },
  rimLight: {
    intensity: 3.5,
    colorHex: '#00e5ff',
    angleDeg: 135
  },
  environmentHdri: 'studio_neutral_4k',
  acesTonemapping: true,
  exposure: 1.0
}

export const DEFAULT_PORTRAIT_CAMERA: PortraitCameraConfig = {
  focalLengthMm: 85,
  apertureFStop: 1.8,
  focusDistanceMeters: 1.5,
  sensorSizeMm: 36,
  iso: 100,
  shutterSpeed: '1/125',
  whiteBalanceK: 5600
}

export const DEFAULT_FACS_EXPRESSIONS: FacsExpressionConfig = {
  neutral: 1.0,
  jawOpen: 0.0,
  mouthWide: 0.0,
  eyeBlinkLeft: 0.0,
  eyeBlinkRight: 0.0,
  browInnerUp: 0.0,
  browLowerer: 0.0,
  cheekRaiser: 0.0,
  noseWrinkler: 0.0,
  lipStretcher: 0.0
}

export const QUALITY_PRESETS = {
  HIGH_8K: { width: 7680, height: 4320, float32Buffer: true, samples: 16 },
  ULTRA_4K: { width: 3840, height: 2160, float32Buffer: true, samples: 8 },
  FULL_HD: { width: 1920, height: 1080, float32Buffer: false, samples: 4 }
}
