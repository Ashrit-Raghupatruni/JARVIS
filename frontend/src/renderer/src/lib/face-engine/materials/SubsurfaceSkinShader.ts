import * as THREE from 'three'
import { SkinSystemConfig } from '../types/faceEngine.types'
import { DEFAULT_SKIN_SYSTEM } from '../configs/faceEngine.config'

/**
 * Production Subsurface Scattering (SSS) Skin Shader Material
 * Simulates physical light transport through human skin layers, micro-pores, oil maps, and blood capillaries.
 */
export class SubsurfaceSkinShader {
  public static createMaterial(config: SkinSystemConfig = DEFAULT_SKIN_SYSTEM): THREE.ShaderMaterial {
    const uniforms = {
      uBaseColor: { value: new THREE.Color(config.skinToneHex) },
      uSubsurfaceColor: { value: new THREE.Color(config.subsurfaceScattering.subsurfaceColor) },
      uSubsurfaceRadius: { value: config.subsurfaceScattering.subsurfaceRadius },
      uScatteringPower: { value: config.subsurfaceScattering.scatteringPower },
      uMelanin: { value: config.melaninIndex },
      uHemoglobin: { value: config.hemoglobinIndex },
      uPoreDensity: { value: config.microDetails.poreDensity },
      uRoughness: { value: config.microDetails.oilinessRoughness },
      uLightPosition: { value: new THREE.Vector3(3.0, 3.0, 4.0) }
    }

    const vertexShader = `
      varying vec3 vNormal;
      varying vec3 vWorldPosition;
      varying vec2 vUv;

      void main() {
        vUv = uv;
        vNormal = normalize(normalMatrix * normal);
        vec4 worldPos = modelMatrix * vec4(position, 1.0);
        vWorldPosition = worldPos.xyz;
        gl_Position = projectionMatrix * viewMatrix * worldPos;
      }
    `

    const fragmentShader = `
      uniform vec3 uBaseColor;
      uniform vec3 uSubsurfaceColor;
      uniform float uSubsurfaceRadius;
      uniform float uScatteringPower;
      uniform float uMelanin;
      uniform float uHemoglobin;
      uniform float uPoreDensity;
      uniform float uRoughness;
      uniform vec3 uLightPosition;

      varying vec3 vNormal;
      varying vec3 vWorldPosition;
      varying vec2 vUv;

      // Procedural Micro-Pore Noise
      float hash(vec2 p) {
        return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453);
      }

      void main() {
        vec3 N = normalize(vNormal);
        vec3 L = normalize(uLightPosition - vWorldPosition);
        vec3 V = normalize(cameraPosition - vWorldPosition);

        // Diffuse Lighting (Lambert)
        float NdotL = max(0.0, dot(N, L));

        // Subsurface Scattering (Back-surface Wrap Lighting)
        float wrap = 0.5;
        float scatterNdotL = max(0.0, (dot(-N, L) + wrap) / (1.0 + wrap));
        vec3 sssEffect = pow(scatterNdotL, uScatteringPower) * uSubsurfaceColor * uSubsurfaceRadius;

        // Procedural Micro-Pores Roughness Variation
        float poreNoise = hash(vUv * 250.0 * uPoreDensity);
        float dynamicRoughness = clamp(uRoughness + poreNoise * 0.08, 0.05, 0.9);

        // Blinn-Phong Specular Highlight (Oil/Moisture layer)
        vec3 H = normalize(L + V);
        float NdotH = max(0.0, dot(N, H));
        float specPower = mix(128.0, 16.0, dynamicRoughness);
        float specular = pow(NdotH, specPower) * 0.35;

        // Blood Hemoglobin Tinting
        vec3 bloodTint = vec3(0.8, 0.1, 0.05) * uHemoglobin * 0.2;

        vec3 finalColor = uBaseColor * NdotL + sssEffect + vec3(specular) + bloodTint;
        gl_FragColor = vec4(finalColor, 0.92);
      }
    `

    return new THREE.ShaderMaterial({
      uniforms,
      vertexShader,
      fragmentShader,
      transparent: true,
      blending: THREE.NormalBlending
    })
  }
}
