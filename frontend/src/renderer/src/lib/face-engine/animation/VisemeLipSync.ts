/**
 * Standard Speech Viseme Mapping Interface
 */
export interface VisemeWeights {
  viseme_sil: number // Silence
  viseme_PP: number  // p, b, m
  viseme_FF: number  // f, v
  viseme_TH: number  // th
  viseme_DD: number  // d, t, n
  viseme_kk: number  // k, g
  viseme_CH: number  // ch, j, sh
  viseme_SS: number  // s, z
  viseme_nn: number  // n, l
  viseme_RR: number  // r
  viseme_aa: number  // a (open)
  viseme_E: number   // e
  viseme_I: number   // i
  viseme_O: number   // o
  viseme_U: number   // u
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
   */
  public static applyToMesh(
    mesh: THREE.Mesh | null,
    dict: { [key: string]: number },
    weights: VisemeWeights
  ): void {
    if (!mesh || !mesh.morphTargetInfluences) return

    const apply = (name: string, val: number) => {
      const idx = dict[name]
      if (idx !== undefined && mesh.morphTargetInfluences) {
        mesh.morphTargetInfluences[idx] = val
      }
    }

    apply('jawOpen', weights.jawOpen)
    apply('viseme_aa', weights.viseme_aa)
    apply('viseme_E', weights.viseme_E)
    apply('viseme_O', weights.viseme_O)
    apply('viseme_FF', weights.viseme_FF)
    apply('viseme_PP', weights.viseme_PP)
  }
}
