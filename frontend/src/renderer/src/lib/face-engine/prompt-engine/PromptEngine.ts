import { PromptEngineInput, GeneratedPromptOutput } from '../types/faceEngine.types'

/**
 * Modular Production Prompt Generator
 * Formulates detailed, structured prompts adhering to photorealistic lighting,
 * camera settings, skin micro-details, and quality weighting.
 */
export class PromptEngine {
  private static readonly UNIVERSAL_QUALITY_MODIFIERS = [
    '8K resolution',
    'UHD',
    '85mm portrait lens',
    'shallow depth of field',
    'sharp focus',
    'studio three-point lighting',
    'subsurface scattering',
    'detailed skin pores',
    'photorealistic rendering',
    'cinematic color grading'
  ]

  private static readonly UNIVERSAL_NEGATIVE_PROMPTS = [
    '(worst quality, low quality, low resolution:1.4)',
    '(blurry:1.2)',
    '(cartoon, anime, 3d render, cgi, illustration:1.3)',
    '(bad anatomy, wrong anatomy:1.3)',
    '(bad face, deformed face, disfigured:1.3)',
    '(plastic skin, poreless skin, waxy skin, airbrushed:1.4)',
    '(asymmetrical, distorted features:1.2)',
    'extra limbs',
    'floating ears',
    'text',
    'watermark',
    'signature'
  ]

  /**
   * Generates a fully optimized positive and negative prompt with recommended sampler settings.
   */
  public generate(input: PromptEngineInput): GeneratedPromptOutput {
    this.validateInput(input)

    const anatomyPhrase = `${input.age}-year-old ${input.ethnicity} ${input.gender}`
    const skinPhrase = `${input.skinToneDescriptor} skin tone with visible pores, subtle skin texture, and natural translucency`
    const eyePhrase = `large ${input.eyeColor} eyes with defined eyelids and realistic catch lights`
    const hairPhrase = `${input.hairStyle} ${input.hairColor} hair with individual strands and natural highlights`
    const expressionPhrase = `${input.expression} expression with subtle micro-emotions`
    const cameraPhrase = `shot on ${input.cameraLens} f/1.8 lens, shallow DOF, crystal clear focus`
    const lightingPhrase = this.getLightingPhrase(input.lightingPreset)

    const accessoryPhrase = input.accessories && input.accessories.length > 0
      ? `wearing ${input.accessories.join(', ')}`
      : ''

    const envPhrase = input.environment ? `in ${input.environment}` : 'neutral studio background'

    const corePrompt = [
      `Ultra-detailed photorealistic headshot portrait of a ${anatomyPhrase}`,
      skinPhrase,
      eyePhrase,
      hairPhrase,
      expressionPhrase,
      accessoryPhrase,
      envPhrase,
      cameraPhrase,
      lightingPhrase,
      ...PromptEngine.UNIVERSAL_QUALITY_MODIFIERS
    ].filter(Boolean).join(', ')

    const negativePrompt = PromptEngine.UNIVERSAL_NEGATIVE_PROMPTS.join(', ')

    return {
      positivePrompt: corePrompt,
      negativePrompt,
      cfgScale: input.qualityPreset === 'photorealistic' ? 5.5 : 4.0,
      samplingSteps: 30,
      sampler: 'DPM++ 2M Karras',
      targetResolution: input.qualityPreset === 'photorealistic'
        ? { width: 1024, height: 1280 }
        : { width: 1024, height: 1024 },
      seed: Math.floor(Math.random() * 2147483647)
    }
  }

  private getLightingPhrase(preset: string): string {
    switch (preset) {
      case 'rembrandt':
        return 'Rembrandt studio lighting with 45-degree key light and triangle cheek highlight'
      case 'golden-hour':
        return 'warm golden hour sunlight with soft diffused fill and rim highlights'
      case 'cinematic':
        return 'dramatic cinematic lighting with high contrast rim light and soft ambient shadow fill'
      case 'three-point':
      default:
        return 'professional three-point studio lighting with key light, soft fill, and cyan rim light'
    }
  }

  private validateInput(input: PromptEngineInput): void {
    if (input.age < 0 || input.age > 120) {
      throw new Error(`Invalid age parameter: ${input.age}. Must be between 0 and 120.`)
    }
    if (!input.ethnicity || input.ethnicity.trim() === '') {
      throw new Error('Ethnicity field cannot be empty.')
    }
  }
}
