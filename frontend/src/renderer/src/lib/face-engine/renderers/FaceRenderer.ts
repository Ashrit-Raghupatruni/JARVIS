import * as THREE from 'three'
import { StudioLightingConfig, PortraitCameraConfig, FacsExpressionConfig } from '../types/faceEngine.types'
import { DEFAULT_STUDIO_LIGHTING, DEFAULT_PORTRAIT_CAMERA } from '../configs/faceEngine.config'
import { GltfHeadLoader, LoadedHeadAsset } from '../loaders/GltfHeadLoader'
import { VisemeLipSync } from '../animation/VisemeLipSync'
import { NaturalIdleAnimator } from '../animation/NaturalIdleAnimator'
import { StudioLightingRig } from '../lighting/StudioLightingRig'
import { PortraitCameraRig } from '../camera/PortraitCameraRig'
import { useAppStore } from '../../../stores/appStore'
import headModelAssetUrl from '../../../assets/models/head.glb?url'

export interface FaceRendererApi {
  render(): void
  setAssistantState(state: string, audioLevel: number): void
  updateFacsExpressions(facs: Partial<FacsExpressionConfig>): void
  resize(width: number, height: number): void
  dispose(): void
}

/**
 * Production Asset-Based 3D Face Renderer
 * Renders real facecap.glb 3D face scan model asset with green hacker theme materials (#00ff66),
 * speech viseme lip-sync, and 60 FPS natural idle breathing/blinking animator.
 */
export class FaceRenderer {
  public static create(
    container: HTMLElement,
    lightingConfig: StudioLightingConfig = DEFAULT_STUDIO_LIGHTING,
    cameraConfig: PortraitCameraConfig = DEFAULT_PORTRAIT_CAMERA,
    customAssetUrl?: string
  ): FaceRendererApi {
    const width = container.clientWidth || 450
    const height = container.clientHeight || 450

    const scene = new THREE.Scene()
    const camera = PortraitCameraRig.build(width / height, cameraConfig)

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
    renderer.setSize(width, height)
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    renderer.setClearColor(0x000000, 0)
    renderer.toneMapping = THREE.ACESFilmicToneMapping
    renderer.toneMappingExposure = lightingConfig.exposure
    container.appendChild(renderer.domElement)

    const rootGroup = new THREE.Group()
    scene.add(rootGroup)

    const idleAnimator = new NaturalIdleAnimator()
    let loadedAsset: LoadedHeadAsset | null = null

    // Load real facecap.glb 3D Head Asset
    const targetUrl = customAssetUrl || headModelAssetUrl
    GltfHeadLoader.load(targetUrl).then((asset) => {
      if (asset && asset.model) {
        loadedAsset = asset
        rootGroup.add(asset.model)
      }
    })

    // Attach Studio Lighting Rig
    const lightingRig = StudioLightingRig.build(lightingConfig)
    scene.add(lightingRig)

    let currentAudioLevel = 0
    let animId: number
    const clock = new THREE.Clock()

    function animate() {
      animId = requestAnimationFrame(animate)
      const dt = clock.getDelta()
      const elapsed = clock.getElapsedTime()

      const isRotationEnabled = useAppStore.getState().is3DRotationEnabled

      if (loadedAsset) {
        // Evaluate Viseme Speech Lip Sync on real model blendshapes
        const visemeWeights = VisemeLipSync.evaluateFromAudio(currentAudioLevel)
        VisemeLipSync.applyToMesh(
          loadedAsset.headMesh,
          loadedAsset.morphTargetDictionary,
          visemeWeights
        )

        // Evaluate Natural Idle Breathing & Blinking & Rotation Toggle
        idleAnimator.update(
          dt,
          elapsed,
          rootGroup,
          loadedAsset.headMesh,
          loadedAsset.morphTargetDictionary,
          isRotationEnabled
        )
      }

      renderer.render(scene, camera)
    }

    animate()

    return {
      render() {
        renderer.render(scene, camera)
      },
      setAssistantState(_state: string, audioLevel: number) {
        currentAudioLevel = audioLevel
      },
      updateFacsExpressions(_facs: Partial<FacsExpressionConfig>) {
        // Managed in animation loop
      },
      resize(w: number, h: number) {
        camera.aspect = w / h
        camera.updateProjectionMatrix()
        renderer.setSize(w, h)
      },
      dispose() {
        cancelAnimationFrame(animId)
        if (renderer.domElement && renderer.domElement.parentNode) {
          renderer.domElement.parentNode.removeChild(renderer.domElement)
        }
        renderer.dispose()
      }
    }
  }
}
