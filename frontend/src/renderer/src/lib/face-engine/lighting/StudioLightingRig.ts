import * as THREE from 'three'
import { StudioLightingConfig } from '../types/faceEngine.types'
import { DEFAULT_STUDIO_LIGHTING } from '../configs/faceEngine.config'

/**
 * Production Studio 3-Point Lighting Rig
 * Features Key Light, Soft Fill Light, Rim Backlight, Kelvin color temperature conversion, and ACES Tonemapping.
 */
export class StudioLightingRig {
  public static build(config: StudioLightingConfig = DEFAULT_STUDIO_LIGHTING): THREE.Group {
    const lightGroup = new THREE.Group()

    // 1. Ambient Fill Light
    const ambient = new THREE.AmbientLight(0x004488, 1.8)
    lightGroup.add(ambient)

    // 2. Key Light (45-degree Studio Key)
    const keyColor = StudioLightingRig.kelvinToColor(config.keyLight.colorTemperatureK)
    const keyLight = new THREE.DirectionalLight(keyColor, config.keyLight.intensity)
    keyLight.position.set(3.5, 3.5, 4.0)
    keyLight.castShadow = true
    lightGroup.add(keyLight)

    // 3. Fill Light (-45-degree Fill)
    const fillColor = StudioLightingRig.kelvinToColor(config.fillLight.colorTemperatureK)
    const fillLight = new THREE.DirectionalLight(fillColor, config.fillLight.intensity)
    fillLight.position.set(-3.5, 1.5, 3.0)
    lightGroup.add(fillLight)

    // 4. Rim Backlight (Cyan / User Accent Rim)
    const rimLight = new THREE.DirectionalLight(new THREE.Color(config.rimLight.colorHex), config.rimLight.intensity)
    rimLight.position.set(-2.0, 3.0, -3.5)
    lightGroup.add(rimLight)

    return lightGroup
  }

  /**
   * Converts Kelvin Color Temperature (e.g. 3200K warm tungsten, 5600K daylight, 6500K cool sky) to THREE.Color.
   */
  public static kelvinToColor(kelvin: number): THREE.Color {
    const temp = kelvin / 100
    let red: number, green: number, blue: number

    if (temp <= 66) {
      red = 255
      green = Math.min(255, Math.max(0, 99.4708025861 * Math.log(temp) - 161.1195681661))
      blue = temp <= 19 ? 0 : Math.min(255, Math.max(0, 138.5177312231 * Math.log(temp - 10) - 305.0447927307))
    } else {
      red = Math.min(255, Math.max(0, 329.698727446 * Math.pow(temp - 60, -0.1332047592)))
      green = Math.min(255, Math.max(0, 288.1221695283 * Math.pow(temp - 60, -0.0755148492)))
      blue = 255
    }

    return new THREE.Color(red / 255, green / 255, blue / 255)
  }
}
