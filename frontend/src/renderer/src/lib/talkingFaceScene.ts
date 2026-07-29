import { FaceRenderer, FaceRendererApi } from './face-engine/renderers/FaceRenderer'

export interface TalkingFaceSceneApi {
  setAssistantState(state: string, audioLevel: number): void
  rotateBy(deltaTheta: number, deltaPhi: number): void
  zoomBy(factor: number): void
  dispose(): void
}

/**
 * Creates and mounts the production 3D Face Engine inside the container element.
 */
export function createTalkingFaceScene(container: HTMLElement): TalkingFaceSceneApi {
  const engineApi: FaceRendererApi = FaceRenderer.create(container)

  const handleResize = () => {
    if (!container) return
    const w = container.clientWidth || 450
    const h = container.clientHeight || 450
    engineApi.resize(w, h)
  }
  window.addEventListener('resize', handleResize)

  return {
    setAssistantState(state: string, audioLevel: number) {
      engineApi.setAssistantState(state, audioLevel)
    },
    rotateBy(_deltaTheta: number, _deltaPhi: number) {
      // Managed by FaceRenderer 360-degree rotation engine
    },
    zoomBy(_factor: number) {
      // Managed by FaceRenderer camera optics
    },
    dispose() {
      window.removeEventListener('resize', handleResize)
      engineApi.dispose()
    }
  }
}
