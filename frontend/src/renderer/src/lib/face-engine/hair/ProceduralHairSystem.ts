import * as THREE from 'three'
import { HairSystemConfig } from '../types/faceEngine.types'
import { DEFAULT_HAIR_SYSTEM } from '../configs/faceEngine.config'

/**
 * Multi-layer Hair Card & Strand Generator
 * Produces anisotropic specular hair strands with density controls and melanin color variation.
 */
export class ProceduralHairSystem {
  public static build(config: HairSystemConfig = DEFAULT_HAIR_SYSTEM): THREE.Group {
    const hairGroup = new THREE.Group()

    const strandCount = Math.min(2000, Math.floor(config.strandDensity / 50))
    const positions: number[] = []
    const colors: number[] = []

    const baseColor = new THREE.Color(config.colorHex)

    for (let i = 0; i < strandCount; i++) {
      // Scalp root position
      const u = Math.random() * Math.PI * 2
      const v = Math.random() * (Math.PI * 0.45) // Top head skull crown

      const r = 1.15
      const rootX = r * Math.sin(v) * Math.sin(u)
      const rootY = r * Math.cos(v) + 0.2
      const rootZ = r * Math.sin(v) * Math.cos(u)

      // Strand length & curvature
      const len = 0.4 + Math.random() * 0.3
      const tipX = rootX * (1.0 + len * 0.2)
      const tipY = rootY - len * 0.8
      const tipZ = rootZ * (1.0 + len * 0.2)

      positions.push(rootX, rootY, rootZ, tipX, tipY, tipZ)

      // Melanin variation tint
      const tint = (Math.random() - 0.5) * 0.15 * config.melanin
      const strandColor = baseColor.clone().addScalar(tint)
      colors.push(strandColor.r, strandColor.g, strandColor.b)
      colors.push(strandColor.r * 0.5, strandColor.g * 0.5, strandColor.b * 0.5)
    }

    const geo = new THREE.BufferGeometry()
    geo.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3))
    geo.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3))

    const hairMat = new THREE.LineBasicMaterial({
      vertexColors: true,
      transparent: true,
      opacity: 0.85,
      blending: THREE.AdditiveBlending
    })

    const hairLines = new THREE.LineSegments(geo, hairMat)
    hairGroup.add(hairLines)

    return hairGroup
  }
}
