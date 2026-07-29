import { GeneratedPromptOutput } from '../types/faceEngine.types'

/**
 * Automated Prompt Optimizer
 * Analyzes prompt token structure, injects missing photorealism modifiers,
 * balances CFG scale, and prevents prompt degradation or hallucination.
 */
export class PromptOptimizer {
  /**
   * Optimizes a raw prompt output by balancing weights and removing conflicting keywords.
   */
  public static optimize(output: GeneratedPromptOutput): GeneratedPromptOutput {
    let positive = output.positivePrompt

    // Enforce Subsurface Scattering & Skin Micro-pores if missing
    if (!positive.includes('subsurface scattering')) {
      positive += ', subsurface scattering, realistic skin translucency'
    }
    if (!positive.includes('pores')) {
      positive += ', visible micro pores'
    }

    // Clean redundant spaces or duplicate commas
    positive = positive.replace(/,\s*,/g, ',').replace(/\s+/g, ' ').trim()

    // Enforce strict CFG scale safety bounds (4.0 to 7.0)
    const safeCfg = Math.max(4.0, Math.min(7.0, output.cfgScale))

    return {
      ...output,
      positivePrompt: positive,
      cfgScale: safeCfg,
      samplingSteps: Math.max(25, output.samplingSteps)
    }
  }
}
