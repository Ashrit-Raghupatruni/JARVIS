import * as THREE from 'three'

export interface IdleHudSceneApi {
  setAssistantState(state: string, audioLevel: number): void
  rotateBy(deltaTheta: number, deltaPhi: number): void
  zoomBy(factor: number): void
  dispose(): void
}

export function createIdleHudScene(container: HTMLElement): IdleHudSceneApi {
  const width = container.clientWidth || 420
  const height = container.clientHeight || 420

  const scene = new THREE.Scene()
  const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 100)
  camera.position.set(0, 0, 5.2)

  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
  renderer.setSize(width, height)
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
  renderer.setClearColor(0x000000, 0)
  container.appendChild(renderer.domElement)

  const group = new THREE.Group()
  scene.add(group)

  // ── Cyan Neon Materials ───────────────────────────────────────────────────
  const brightMat = new THREE.LineBasicMaterial({
    color: 0x00e5ff,
    transparent: true,
    opacity: 0.95,
    blending: THREE.AdditiveBlending
  })

  const dimMat = new THREE.LineBasicMaterial({
    color: 0x0066aa,
    transparent: true,
    opacity: 0.5,
    blending: THREE.AdditiveBlending
  })

  const faintMat = new THREE.LineBasicMaterial({
    color: 0x002244,
    transparent: true,
    opacity: 0.35,
    blending: THREE.AdditiveBlending
  })

  // ── 1. Outer Notched Ring (80 Teeth) ───────────────────────────────────────
  const R_OUT = 2.1
  const teethGroup = new THREE.Group()

  const outerCircleGeo = new THREE.BufferGeometry()
  const ptsOuter: THREE.Vector3[] = []
  for (let i = 0; i <= 120; i++) {
    const a = (i / 120) * Math.PI * 2
    ptsOuter.push(new THREE.Vector3(R_OUT * Math.cos(a), R_OUT * Math.sin(a), 0))
  }
  outerCircleGeo.setFromPoints(ptsOuter)
  const outerLine = new THREE.LineLoop(outerCircleGeo, dimMat)
  teethGroup.add(outerLine)

  const teethPts: THREE.Vector3[] = []
  for (let i = 0; i < 80; i++) {
    const a = (i / 80) * Math.PI * 2
    const len = i % 10 === 0 ? 0.14 : i % 5 === 0 ? 0.09 : 0.05
    teethPts.push(new THREE.Vector3(R_OUT * Math.cos(a), R_OUT * Math.sin(a), 0))
    teethPts.push(new THREE.Vector3((R_OUT + len) * Math.cos(a), (R_OUT + len) * Math.sin(a), 0))
  }
  const teethGeo = new THREE.BufferGeometry().setFromPoints(teethPts)
  const teeth = new THREE.LineSegments(teethGeo, brightMat)
  teethGroup.add(teeth)
  group.add(teethGroup)

  // ── 2. Middle Ticking LED Ring ──────────────────────────────────────────────
  const R_MID = 1.8
  const dotsGroup = new THREE.Group()
  const dotCount = 24
  const dotGeo = new THREE.BufferGeometry()
  const dotPositions: number[] = []
  for (let i = 0; i < dotCount; i++) {
    const a = (i / dotCount) * Math.PI * 2
    dotPositions.push(R_MID * Math.cos(a), R_MID * Math.sin(a), 0)
  }
  dotGeo.setAttribute('position', new THREE.Float32BufferAttribute(dotPositions, 3))
  const dotMat = new THREE.PointsMaterial({
    color: 0x00e5ff,
    size: 0.08,
    transparent: true,
    opacity: 0.9,
    blending: THREE.AdditiveBlending
  })
  const dots = new THREE.Points(dotGeo, dotMat)
  dotsGroup.add(dots)

  // Concentric arc segments
  function makeArc(radius: number, start: number, end: number, segs = 30) {
    const pts: THREE.Vector3[] = []
    for (let i = 0; i <= segs; i++) {
      const a = start + (i / segs) * (end - start)
      pts.push(new THREE.Vector3(radius * Math.cos(a), radius * Math.sin(a), 0))
    }
    return new THREE.BufferGeometry().setFromPoints(pts)
  }

  const arc1 = new THREE.Line(makeArc(R_MID, 0.2, 1.8), brightMat)
  const arc2 = new THREE.Line(makeArc(R_MID, 2.2, 4.0), brightMat)
  const arc3 = new THREE.Line(makeArc(R_MID, 4.4, 5.8), brightMat)
  dotsGroup.add(arc1, arc2, arc3)
  group.add(dotsGroup)

  // ── 3. Inner Concentric Tech Rings ─────────────────────────────────────────
  const R_INNER = 1.45
  const innerRingGroup = new THREE.Group()

  const innerCircleGeo = new THREE.BufferGeometry()
  const ptsInner: THREE.Vector3[] = []
  for (let i = 0; i <= 100; i++) {
    const a = (i / 100) * Math.PI * 2
    ptsInner.push(new THREE.Vector3(R_INNER * Math.cos(a), R_INNER * Math.sin(a), 0))
  }
  innerCircleGeo.setFromPoints(ptsInner)
  const innerLine = new THREE.LineLoop(innerCircleGeo, faintMat)
  innerRingGroup.add(innerLine)
  group.add(innerRingGroup)

  // ── 4. Floating Ambient Particle Atmosphere ──────────────────────────────
  const partCount = 120
  const partGeo = new THREE.BufferGeometry()
  const partPos: number[] = []
  for (let i = 0; i < partCount; i++) {
    const r = 0.5 + Math.random() * 1.7
    const theta = Math.random() * Math.PI * 2
    const z = (Math.random() - 0.5) * 0.8
    partPos.push(r * Math.cos(theta), r * Math.sin(theta), z)
  }
  partGeo.setAttribute('position', new THREE.Float32BufferAttribute(partPos, 3))
  const partMat = new THREE.PointsMaterial({
    color: 0x99f5ff,
    size: 0.04,
    transparent: true,
    opacity: 0.7,
    blending: THREE.AdditiveBlending
  })
  const particles = new THREE.Points(partGeo, partMat)
  group.add(particles)

  // ── Animation Loop ───────────────────────────────────────────────────────
  let animId: number
  let clock = new THREE.Clock()
  let currentState = 'idle'
  let currentAudioLevel = 0

  function animate() {
    animId = requestAnimationFrame(animate)
    const dt = clock.getDelta()
    const elapsed = clock.getElapsedTime()

    teethGroup.rotation.z -= dt * 0.15
    dotsGroup.rotation.z += dt * 0.22

    const pulse = 1.0 + Math.sin(elapsed * 2.0) * 0.03 + currentAudioLevel * 0.15
    innerRingGroup.scale.set(pulse, pulse, pulse)

    particles.rotation.z += dt * 0.05

    if (currentState === 'listening') {
      teethGroup.rotation.z -= dt * 0.4
      dotMat.size = 0.1 + Math.sin(elapsed * 6.0) * 0.04
    } else if (currentState === 'processing') {
      dotsGroup.rotation.z += dt * 0.8
    } else {
      dotMat.size = 0.08
    }

    renderer.render(scene, camera)
  }

  animate()

  const handleResize = () => {
    if (!container) return
    const w = container.clientWidth || 420
    const h = container.clientHeight || 420
    camera.aspect = w / h
    camera.updateProjectionMatrix()
    renderer.setSize(w, h)
  }
  window.addEventListener('resize', handleResize)

  return {
    setAssistantState(state: string, audioLevel: number) {
      currentState = state
      currentAudioLevel = audioLevel
    },
    rotateBy(deltaTheta: number, deltaPhi: number) {
      group.rotation.y += deltaTheta
      group.rotation.x += deltaPhi
    },
    zoomBy(factor: number) {
      camera.position.z = THREE.MathUtils.clamp(camera.position.z * factor, 2.5, 10.0)
    },
    dispose() {
      cancelAnimationFrame(animId)
      window.removeEventListener('resize', handleResize)
      if (renderer.domElement && renderer.domElement.parentNode) {
        renderer.domElement.parentNode.removeChild(renderer.domElement)
      }
      renderer.dispose()
    }
  }
}
