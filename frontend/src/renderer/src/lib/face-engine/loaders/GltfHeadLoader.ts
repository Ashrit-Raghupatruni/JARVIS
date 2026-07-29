import * as THREE from 'three'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import headModelAssetUrl from '../../../assets/models/head.glb?url'

export interface LoadedHeadAsset {
  model: THREE.Group
  headMesh: THREE.Mesh | null
  morphTargetDictionary: { [key: string]: number }
  morphTargetInfluences: number[]
}

/**
 * Production Asset-Based GLTF / GLB / VRM 3D Head Loader
 * Renders smooth organic oval human head shape with natural skin tone. Zero rectangular box edges.
 */
export class GltfHeadLoader {
  /**
   * Constructs a smooth organic oval 3D Head mesh with natural skin tone.
   */
  public static createImmediateHead(): LoadedHeadAsset {
    const group = new THREE.Group()
    const geo = new THREE.BufferGeometry()

    const widthSegments = 64
    const heightSegments = 64

    const basePositions: number[] = []
    const jawOpenPos: number[] = []
    const mouthWidePos: number[] = []
    const eyeBlinkPos: number[] = []
    const indices: number[] = []

    for (let y = 0; y <= heightSegments; y++) {
      const v = y / heightSegments
      const phi = v * Math.PI

      for (let x = 0; x <= widthSegments; x++) {
        const u = x / widthSegments
        const theta = u * Math.PI * 2

        // Smooth Organic Oval Ellipsoid Base (Human Cranium)
        let px = 1.0 * Math.sin(phi) * Math.sin(theta)
        let py = 1.35 * Math.cos(phi)
        let pz = 1.08 * Math.sin(phi) * Math.cos(theta)

        // Smooth Back Skull Flattening
        if (pz < 0) pz *= 0.85

        // Smooth Forehead Curve
        if (py > 0.35 && pz > 0) pz += (py - 0.35) * 0.12

        // Smooth Eyebrow Ridge
        if (py > 0.32 && py < 0.44 && Math.abs(px) > 0.15 && Math.abs(px) < 0.65 && pz > 0.3) {
          const ridge = (1.0 - Math.abs(py - 0.38) / 0.06) * (1.0 - Math.abs(Math.abs(px) - 0.4) / 0.25)
          pz += ridge * 0.18
        }

        // Smooth Eye Sockets
        const distEye = Math.hypot(Math.abs(px) - 0.38, py - 0.26)
        if (distEye < 0.25 && pz > 0.2) {
          pz -= Math.cos((distEye / 0.25) * (Math.PI / 2)) * 0.22
        }

        // Smooth Nose Bridge & Nostrils
        if (py > -0.15 && py < 0.35 && Math.abs(px) < 0.3 && pz > 0.22) {
          const noseFactor = (1.0 - Math.abs(px) / 0.3) * Math.sin(((py + 0.15) / 0.5) * Math.PI)
          pz += noseFactor * 0.38
          if (py < 0.05) px *= 1.1
        }

        // Smooth Cheekbones
        if (py > 0.0 && py < 0.25 && Math.abs(px) > 0.45 && pz > 0.2) {
          pz += (1.0 - Math.abs(py - 0.12) / 0.12) * (1.0 - Math.abs(Math.abs(px) - 0.6) / 0.2) * 0.15
        }

        // Smooth Curved Ears (Organic Gaussian Falloff)
        const earDist = Math.hypot(Math.abs(px) - 0.95, py - 0.22)
        if (earDist < 0.32 && pz < 0.2) {
          const earFalloff = Math.cos((earDist / 0.32) * (Math.PI / 2))
          px += Math.sign(px) * earFalloff * 0.24
          pz += earFalloff * 0.08
        }

        // Smooth Lips & Tapered Chin
        if (py > -0.32 && py < -0.12 && Math.abs(px) < 0.4 && pz > 0.3) {
          const lipDist = Math.abs(py - (-0.22))
          if (lipDist < 0.04) pz -= 0.08
          else pz += (1.0 - Math.abs(px) / 0.4) * (1.0 - lipDist / 0.1) * 0.14
        }
        if (py < -0.2) {
          const jawTaper = Math.max(0.45, 1.0 - (Math.abs(py) - 0.2) * 0.45)
          px *= jawTaper
        }

        basePositions.push(px, py, pz)

        // Morph 0: Jaw Open
        let jy = py, jz = pz
        if (py < -0.15 && pz > 0.05) {
          const w = Math.min(1.0, (Math.abs(py) - 0.15) / 0.75)
          jy -= w * 0.45
          jz += w * 0.14
        }
        jawOpenPos.push(px, jy, jz)

        // Morph 1: Mouth Wide
        let wx = px
        if (py > -0.35 && py < -0.12 && pz > 0.25) wx *= 1.2
        mouthWidePos.push(wx, py, pz)

        // Morph 2: Eye Blink
        let by = py
        if (py > 0.22 && py < 0.34 && Math.abs(px) > 0.2 && Math.abs(px) < 0.55 && pz > 0.2) {
          by = 0.24
        }
        eyeBlinkPos.push(px, by, pz)
      }
    }

    for (let y = 0; y < heightSegments; y++) {
      for (let x = 0; x < widthSegments; x++) {
        const first = y * (widthSegments + 1) + x
        const second = first + widthSegments + 1
        indices.push(first, second, first + 1)
        indices.push(second, second + 1, first + 1)
      }
    }

    geo.setIndex(indices)
    geo.setAttribute('position', new THREE.Float32BufferAttribute(basePositions, 3))
    geo.computeVertexNormals()

    geo.morphAttributes.position = [
      new THREE.Float32BufferAttribute(jawOpenPos, 3),
      new THREE.Float32BufferAttribute(mouthWidePos, 3),
      new THREE.Float32BufferAttribute(eyeBlinkPos, 3)
    ]

    // Realistic Smooth Human Skin Tone Material
    const meshMat = new THREE.MeshStandardMaterial({
      color: 0xf0c49e,
      roughness: 0.45,
      metalness: 0.05,
      transparent: false,
      wireframe: false
    })

    const headMesh = new THREE.Mesh(geo, meshMat)
    headMesh.morphTargetInfluences = [0, 0, 0]
    group.add(headMesh)

    // Eye Spheres
    const eyeGeo = new THREE.SphereGeometry(0.11, 20, 20)
    const eyeMat = new THREE.MeshStandardMaterial({
      color: 0xffffff,
      roughness: 0.1,
      metalness: 0.0
    })

    const leftEye = new THREE.Mesh(eyeGeo, eyeMat)
    leftEye.position.set(-0.38, 0.26, 0.36)

    const rightEye = new THREE.Mesh(eyeGeo, eyeMat)
    rightEye.position.set(0.38, 0.26, 0.36)

    group.add(leftEye, rightEye)

    const morphTargetDictionary: { [key: string]: number } = {
      jawOpen: 0,
      viseme_aa: 0,
      mouthSmile: 1,
      eyeBlinkLeft: 2,
      eyeBlinkRight: 2
    }

    return {
      model: group,
      headMesh,
      morphTargetDictionary,
      morphTargetInfluences: headMesh.morphTargetInfluences || [0, 0, 0]
    }
  }

  /**
   * Loads a GLTF/GLB 3D Head Asset asynchronously.
   */
  public static async load(customUrl?: string): Promise<LoadedHeadAsset> {
    const loader = new GLTFLoader()
    const targetUrl = customUrl || headModelAssetUrl || '/models/head.glb'

    return new Promise((resolve) => {
      loader.load(
        targetUrl,
        (gltf) => {
          const model = gltf.scene

          const box = new THREE.Box3().setFromObject(model)
          const center = box.getCenter(new THREE.Vector3())
          const size = box.getSize(new THREE.Vector3())
          const maxDim = Math.max(size.x, size.y, size.z)

          if (maxDim > 0) {
            const scale = 2.0 / maxDim
            model.scale.set(scale, scale, scale)
            model.position.sub(center.multiplyScalar(scale))
          }

          let headMesh: THREE.Mesh | null = null
          let morphTargetDictionary: { [key: string]: number } = {}
          let morphTargetInfluences: number[] = []

          model.traverse((child) => {
            if ((child as THREE.Mesh).isMesh) {
              const mesh = child as THREE.Mesh

              mesh.material = new THREE.MeshStandardMaterial({
                color: 0xf0c49e,
                roughness: 0.45,
                metalness: 0.05,
                transparent: false,
                wireframe: false
              })

              if (mesh.morphTargetDictionary && mesh.morphTargetInfluences) {
                headMesh = mesh
                morphTargetDictionary = mesh.morphTargetDictionary
                morphTargetInfluences = mesh.morphTargetInfluences
              }
            }
          })

          resolve({
            model,
            headMesh,
            morphTargetDictionary,
            morphTargetInfluences
          })
        },
        undefined,
        () => {
          resolve(GltfHeadLoader.createImmediateHead())
        }
      )
    })
  }
}
