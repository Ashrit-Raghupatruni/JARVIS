import * as THREE from 'three'

/**
 * Standard Speech Viseme Mapping Interface
 */
export interface VisemeWeights {
  viseme_sil: number
  viseme_PP: number
  viseme_FF: number
  viseme_TH: number
  viseme_DD: number
  viseme_kk: number
  viseme_CH: number
  viseme_SS: number
  viseme_nn: number
  viseme_RR: number
  viseme_aa: number
  viseme_E: number
  viseme_I: number
  viseme_O: number
  viseme_U: number
  jawOpen: number
}

export class VisemeLipSync {
  /**
   * Evaluates current speech audio amplitude into corresponding viseme blendshape weights.
   */
  public static evaluateFromAudio(audioLevel: number): VisemeWeights {
    const level = Math.max(0, Math.min(1.0, audioLevel * 2.5))

    return {
      viseme_sil: level < 0.05 ? 1.0 : 0.0,
      viseme_PP: level < 0.1 ? 0.8 : 0.0,
      viseme_FF: level >= 0.1 && level < 0.25 ? 0.6 : 0.0,
      viseme_TH: level >= 0.25 && level < 0.4 ? 0.5 : 0.0,
      viseme_DD: level >= 0.4 && level < 0.55 ? 0.7 : 0.0,
      viseme_kk: level >= 0.55 && level < 0.7 ? 0.6 : 0.0,
      viseme_CH: 0.0,
      viseme_SS: 0.0,
      viseme_nn: 0.0,
      viseme_RR: 0.0,
      viseme_aa: level >= 0.7 ? level : 0.0,
      viseme_E: level >= 0.5 ? 0.4 : 0.0,
      viseme_I: 0.0,
      viseme_O: level >= 0.6 ? 0.5 : 0.0,
      viseme_U: 0.0,
      jawOpen: level
    }
  }

  /**
   * Applies computed viseme weights onto a target 3D Mesh's morph target influences.
   * Matches both ARKit `blendShape1.` prefixed keys and standard viseme names.
   */
  public static applyToMesh(
    mesh: THREE.Mesh | null,
    dict: { [key: string]: number },
    weights: VisemeWeights
  ): void {
    if (!mesh || !mesh.morphTargetInfluences) return

    const apply = (targetName: string, val: number) => {
      const idx =
        dict[`blendShape1.${targetName}`] ??
        dict[targetName] ??
        dict[targetName.toLowerCase()]
      if (idx !== undefined && mesh.morphTargetInfluences) {
        mesh.morphTargetInfluences[idx] = val
      }
    }

    apply('jawOpen', weights.jawOpen)
    apply('mouthFunnel', weights.viseme_O)
    apply('mouthPucker', weights.viseme_PP)
    apply('mouthSmile_L', weights.viseme_E * 0.5)
    apply('mouthSmile_R', weights.viseme_E * 0.5)
  }
}
