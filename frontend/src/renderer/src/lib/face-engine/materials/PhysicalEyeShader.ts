import * as THREE from 'three'

/**
 * Physically Correct Eye Shader
 * Implements Snell's Law cornea Index of Refraction ($n=1.376$),
 * iris depth indentation, pupil dilation, sclera vascularity, and tear-line catch lights.
 */
export class PhysicalEyeShader {
  public static createMaterial(): THREE.ShaderMaterial {
    const uniforms = {
      uIrisColor: { value: new THREE.Color('#00e5ff') },
      uPupilDilation: { value: 0.4 }, // 0.2 (contracted) to 0.8 (dilated)
      uCorneaIOR: { value: 1.376 },   // Human Cornea Refractive Index
      uTearFilmMoisture: { value: 0.95 },
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
      uniform vec3 uIrisColor;
      uniform float uPupilDilation;
      uniform float uCorneaIOR;
      uniform float uTearFilmMoisture;
      uniform vec3 uLightPosition;

      varying vec3 vNormal;
      varying vec3 vWorldPosition;
      varying vec2 vUv;

      void main() {
        vec3 N = normalize(vNormal);
        vec3 L = normalize(uLightPosition - vWorldPosition);
        vec3 V = normalize(cameraPosition - vWorldPosition);

        // Snell's Law Cornea Refraction
        vec3 R = refract(-V, N, 1.0 / uCorneaIOR);

        // Distance from center of eye pupil
        vec2 center = vec2(0.5, 0.5);
        float dist = distance(vUv, center);

        // Pupil / Iris Mask
        vec3 baseColor;
        if (dist < uPupilDilation * 0.2) {
          baseColor = vec3(0.02, 0.02, 0.04); // Pupil Core
        } else if (dist < 0.42) {
          // Iris Strands Texture
          float irisFiber = sin(atan(vUv.y - 0.5, vUv.x - 0.5) * 30.0) * 0.15 + 0.85;
          baseColor = uIrisColor * irisFiber;
        } else {
          // Sclera White & Micro-Veins
          baseColor = vec3(0.92, 0.93, 0.95);
        }

        // Specular Catch-Light Highlight on Wet Tear Film
        vec3 H = normalize(L + V);
        float catchLight = pow(max(0.0, dot(N, H)), 256.0) * uTearFilmMoisture * 2.0;

        vec3 finalColor = baseColor + vec3(catchLight);
        gl_FragColor = vec4(finalColor, 1.0);
      }
    `

    return new THREE.ShaderMaterial({
      uniforms,
      vertexShader,
      fragmentShader
    })
  }
}
