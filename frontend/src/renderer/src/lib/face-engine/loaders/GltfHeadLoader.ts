import * as THREE from 'three'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import { MeshoptDecoder } from 'three/examples/jsm/libs/meshopt_decoder.module.js'
import headModelAssetUrl from '../../../assets/models/head.glb?url'

export interface LoadedHeadAsset {
  model: THREE.Group
  headMesh: THREE.Mesh | null
  morphTargetDictionary: { [key: string]: number }
  morphTargetInfluences: number[]
  error?: string
}

/**
 * Production Asset-Based GLTF 3D Head Loader (facecap.glb)
 * Loads real 3D face scan model asset with ARKit morph targets from Three.js examples.
 * Procedural fallback geometry (createImmediateHead) has been ENTIRELY DELETED.
 */
export class GltfHeadLoader {
  /**
   * Asynchronously loads the real facecap.glb 3D Head Asset using GLTFLoader and MeshoptDecoder.
   */
  public static async load(customUrl?: string): Promise<LoadedHeadAsset> {
    const loader = new GLTFLoader()
    loader.setMeshoptDecoder(MeshoptDecoder)

    const targetUrl = customUrl || headModelAssetUrl || '/models/head.glb'

    return new Promise((resolve) => {
      loader.load(
        targetUrl,
        (gltf) => {
          const model = gltf.scene

          let headMesh: THREE.Mesh | null = null
          let morphTargetDictionary: { [key: string]: number } = {}
          let morphTargetInfluences: number[] = []

          model.traverse((child) => {
            if ((child as THREE.Mesh).isMesh) {
              const mesh = child as THREE.Mesh

              // Green Hacker Theme Material (#00ff66)
              mesh.material = new THREE.MeshStandardMaterial({
                color: 0x00ff66,
                emissive: 0x003311,
                roughness: 0.35,
                metalness: 0.15,
                wireframe: false,
                side: THREE.DoubleSide
              })

              if (!headMesh) {
                headMesh = mesh
              }

              if (mesh.morphTargetDictionary && mesh.morphTargetInfluences) {
                // Target the head mesh containing blendShape1 morph targets
                if (mesh.name === 'mesh_2' || Object.keys(mesh.morphTargetDictionary).length > 5) {
                  headMesh = mesh
                  morphTargetDictionary = mesh.morphTargetDictionary
                  morphTargetInfluences = mesh.morphTargetInfluences
                }
              }
            }
          })

          // Auto-scale and center loaded facecap.glb model asset
          const box = new THREE.Box3().setFromObject(model)
          const center = box.getCenter(new THREE.Vector3())
          const size = box.getSize(new THREE.Vector3())
          const maxDim = Math.max(size.x, size.y, size.z)

          if (maxDim > 0) {
            const scale = 2.4 / maxDim
            model.scale.set(scale, scale, scale)
            model.position.sub(center.multiplyScalar(scale))
          }

          resolve({
            model,
            headMesh,
            morphTargetDictionary,
            morphTargetInfluences
          })
        },
        undefined,
        (err) => {
          console.error('Failed to load real 3D facecap.glb asset:', err)
          // Resolve empty container with error flag (Zero procedural math fallback)
          resolve({
            model: new THREE.Group(),
            headMesh: null,
            morphTargetDictionary: {},
            morphTargetInfluences: [],
            error: 'Failed to load facecap.glb 3D face asset'
          })
        }
      )
    })
  }
}
