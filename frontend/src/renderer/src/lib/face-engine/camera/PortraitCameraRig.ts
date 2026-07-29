import * as THREE from 'three'
import { PortraitCameraConfig } from '../types/faceEngine.types'
import { DEFAULT_PORTRAIT_CAMERA } from '../configs/faceEngine.config'

/**
 * Production Portrait Camera Rig
 * Frames head avatar centered nicely inside the main visualizer panel.
 */
export class PortraitCameraRig {
  public static build(
    aspectRatio: number,
    config: PortraitCameraConfig = DEFAULT_PORTRAIT_CAMERA
  ): THREE.PerspectiveCamera {
    const fov = 2 * Math.atan(config.sensorSizeMm / (2 * config.focalLengthMm)) * (180 / Math.PI)

    const camera = new THREE.PerspectiveCamera(fov, aspectRatio, 0.1, 100)
    camera.position.set(0, 0, 4.8)
    camera.lookAt(0, 0, 0)

    return camera
  }
}
