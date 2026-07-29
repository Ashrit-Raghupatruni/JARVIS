import * as THREE from 'three'
import { GltfHeadLoader, LoadedHeadAsset } from '../loaders/GltfHeadLoader'
import { FacsExpressionConfig } from '../types/faceEngine.types'

export interface BuiltFaceAnatomy {
  meshGroup: THREE.Group
  headMesh: THREE.Mesh | null
  morphDict: { [key: string]: number }
  updateExpressions(facs: Partial<FacsExpressionConfig>, audioLevel?: number): void
}

/**
 * Production Asset-Based Facial Anatomy Manager
 * Strictly loads 3D Human Head model assets via GLTFLoader. Zero primitive box/sphere shapes.
 */
export class FacialAnatomyBuilder {
  public static async buildAsync(customUrl?: string): Promise<BuiltFaceAnatomy> {
    const loaded: LoadedHeadAsset = await GltfHeadLoader.load(customUrl)

    return {
      meshGroup: loaded.model,
      headMesh: loaded.headMesh,
      morphDict: loaded.morphTargetDictionary,
      updateExpressions(facs: Partial<FacsExpressionConfig>, audioLevel = 0) {
        if (!loaded.headMesh || !loaded.headMesh.morphTargetInfluences) return

        const dict = loaded.morphTargetDictionary
        const inf = loaded.headMesh.morphTargetInfluences

        const setMorph = (key: string, val: number) => {
          const idx = dict[key]
          if (idx !== undefined && inf[idx] !== undefined) {
            inf[idx] = val
          }
        }

        const jawVal = Math.max(facs.jawOpen || 0, Math.min(1.0, audioLevel * 2.5))
        setMorph('jawOpen', jawVal)
        setMorph('mouthSmile', facs.mouthWide || 0)
        setMorph('eyeBlinkLeft', facs.eyeBlinkLeft || 0)
        setMorph('eyeBlinkRight', facs.eyeBlinkRight || 0)
        setMorph('browInnerUp', facs.browInnerUp || 0)
      }
    }
  }
}
