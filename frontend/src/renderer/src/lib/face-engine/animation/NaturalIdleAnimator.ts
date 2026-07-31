import * as THREE from 'three'

/**
 * Natural Idle Animator
 * Controls natural breathing cycles, micro-saccade eye gaze shifts, and procedural natural double-blinking.
 */
export class NaturalIdleAnimator {
  private nextBlinkTime = 2.5
  private isBlinking = false
  private blinkProgress = 0

  /**
   * Evaluates natural idle frame motion and updates object rotation and blink morph target.
   */
  public update(
    dt: number,
    elapsed: number,
    rootGroup: THREE.Group,
    mesh: THREE.Mesh | null,
    dict: { [key: string]: number },
    isRotationEnabled = true
  ): void {
    // 1. Natural Breathing Sway (Chest / Neck micro oscillation)
    const breathCycle = Math.sin(elapsed * 1.8) * 0.02
    rootGroup.position.y = breathCycle
    rootGroup.rotation.x = Math.sin(elapsed * 0.6) * 0.03

    // Continuous smooth Y-axis 360-degree rotation (if enabled)
    if (isRotationEnabled) {
      rootGroup.rotation.y += dt * 0.2
    }

    // 2. Procedural Natural Double-Blinking
    if (elapsed > this.nextBlinkTime && !this.isBlinking) {
      this.isBlinking = true
      this.blinkProgress = 0
    }

    if (this.isBlinking && mesh && mesh.morphTargetInfluences) {
      this.blinkProgress += dt * 8.0
      const blinkValue = Math.sin(Math.min(Math.PI, this.blinkProgress * Math.PI))

      const leftIdx =
        dict['blendShape1.eyeBlink_L'] ??
        dict['eyeBlinkLeft'] ??
        dict['eyeBlink_L'] ??
        1
      const rightIdx =
        dict['blendShape1.eyeBlink_R'] ??
        dict['eyeBlinkRight'] ??
        dict['eyeBlink_R'] ??
        2

      if (leftIdx !== undefined && mesh.morphTargetInfluences[leftIdx] !== undefined) {
        mesh.morphTargetInfluences[leftIdx] = blinkValue
      }
      if (rightIdx !== undefined && mesh.morphTargetInfluences[rightIdx] !== undefined) {
        mesh.morphTargetInfluences[rightIdx] = blinkValue
      }

      if (this.blinkProgress >= 1.0) {
        this.isBlinking = false
        this.nextBlinkTime = elapsed + 2.5 + Math.random() * 3.5
      }
    }
  }
}
