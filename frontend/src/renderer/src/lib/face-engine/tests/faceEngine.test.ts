import { describe, it, expect } from 'vitest'
import { PromptEngine } from '../prompt-engine/PromptEngine'
import { PromptOptimizer } from '../prompt-engine/PromptOptimizer'
import { VisemeLipSync } from '../animation/VisemeLipSync'
import { QualityValidator } from '../validation/QualityValidator'
import { DEFAULT_FACIAL_ANATOMY, DEFAULT_SKIN_SYSTEM } from '../configs/faceEngine.config'

describe('Asset-Based 3D Face Engine Module Tests', () => {
  it('VisemeLipSync maps audio level to correct viseme blendshapes', () => {
    const silent = VisemeLipSync.evaluateFromAudio(0.0)
    expect(silent.viseme_sil).toBe(1.0)
    expect(silent.jawOpen).toBe(0.0)

    const loud = VisemeLipSync.evaluateFromAudio(0.8)
    expect(loud.jawOpen).toBeGreaterThan(0.5)
    expect(loud.viseme_aa).toBeGreaterThan(0.0)
  })

  it('PromptEngine generates valid photorealistic prompt output', () => {
    const engine = new PromptEngine()
    const output = engine.generate({
      age: 28,
      gender: 'woman',
      ethnicity: 'East Asian',
      skinToneDescriptor: 'porcelain light',
      hairStyle: 'long straight',
      hairColor: 'black',
      eyeColor: 'dark brown',
      expression: 'neutral with subtle smile',
      cameraLens: '85mm',
      lightingPreset: 'three-point',
      qualityPreset: 'photorealistic'
    })

    expect(output.positivePrompt).toContain('East Asian')
    expect(output.positivePrompt).toContain('85mm')
    expect(output.positivePrompt).toContain('subsurface scattering')
    expect(output.negativePrompt).toContain('plastic skin')
    expect(output.cfgScale).toBeGreaterThanOrEqual(4.0)
  })

  it('QualityValidator accurately assesses skin realism & eye bounds', () => {
    const anatomyConfig = JSON.parse(JSON.stringify(DEFAULT_FACIAL_ANATOMY))
    const skinConfig = JSON.parse(JSON.stringify(DEFAULT_SKIN_SYSTEM))

    const reportPass = QualityValidator.validate(anatomyConfig, skinConfig)
    expect(reportPass.passed).toBe(true)
  })
})
