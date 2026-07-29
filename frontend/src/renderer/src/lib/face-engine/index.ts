/**
 * Unified Public Entry Point for Asset-Based 3D Face Engine
 */

export * from './types/faceEngine.types'
export * from './configs/faceEngine.config'
export * from './loaders/GltfHeadLoader'
export * from './animation/VisemeLipSync'
export * from './animation/NaturalIdleAnimator'
export * from './prompt-engine/PromptEngine'
export * from './prompt-engine/PromptOptimizer'
export * from './anatomy/FacialAnatomyBuilder'
export * from './materials/SubsurfaceSkinShader'
export * from './materials/PhysicalEyeShader'
export * from './hair/ProceduralHairSystem'
export * from './lighting/StudioLightingRig'
export * from './camera/PortraitCameraRig'
export * from './validation/QualityValidator'
export * from './renderers/FaceRenderer'
