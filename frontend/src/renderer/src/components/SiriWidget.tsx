import React, { useEffect, useRef, useState } from 'react'
import type { AssistantState } from '../types'

interface WaveParams {
  color: string
  alpha: number
  frequency: number
  amplitude: number
  speed: number
  phase: number
}

const SiriWidget: React.FC = () => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const [state, setState] = useState<AssistantState>('idle')
  const [audioLevel, setAudioLevel] = useState(0)

  // Listen to IPC updates from the main process
  useEffect(() => {
    const api = (window as any).electronAPI
    if (api?.onStatusUpdate) {
      const unsubscribe = api.onStatusUpdate((data: { state: AssistantState; audioLevel: number }) => {
        setState(data.state)
        setAudioLevel(data.audioLevel)
      })
      return unsubscribe
    }
    return undefined
  }, [])

  // Animating the waves on canvas
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    let animationFrameId: number

    // Define the waves with Siri-like brand neon colors
    const waves: WaveParams[] = [
      { color: '0, 229, 255', alpha: 0.8, frequency: 0.012, amplitude: 10, speed: 0.08, phase: 0 },   // Cyan
      { color: '213, 0, 249', alpha: 0.7, frequency: 0.018, amplitude: 8, speed: -0.06, phase: 2 },  // Purple/Magenta
      { color: '0, 174, 255', alpha: 0.6, frequency: 0.008, amplitude: 12, speed: 0.04, phase: 4 },  // Bright Blue
      { color: '255, 170, 0', alpha: 0.5, frequency: 0.015, amplitude: 6, speed: -0.05, phase: 1 }   // Neon Orange/Yellow
    ]

    const resizeCanvas = (): void => {
      const rect = canvas.getBoundingClientRect()
      canvas.width = rect.width * window.devicePixelRatio
      canvas.height = rect.height * window.devicePixelRatio
      ctx.scale(window.devicePixelRatio, window.devicePixelRatio)
    }

    resizeCanvas()
    window.addEventListener('resize', resizeCanvas)

    const render = (): void => {
      const width = canvas.width / window.devicePixelRatio
      const height = canvas.height / window.devicePixelRatio

      ctx.clearRect(0, 0, width, height)

      // Use screen composite mode for organic glowing overlays
      ctx.globalCompositeOperation = 'screen'

      // Set baseline values depending on the state
      let baseAmplitude = 0
      let baseSpeedMultiplier = 0.5
      let baseFrequencyMultiplier = 1.0

      if (state === 'wake_word_detected') {
        baseAmplitude = 12
        baseSpeedMultiplier = 2.5
        baseFrequencyMultiplier = 1.5
      } else if (state === 'listening') {
        // Amplitude scales directly with audio volume, flat if quiet
        baseAmplitude = audioLevel * 50
        baseSpeedMultiplier = 1.0 + audioLevel * 3
        baseFrequencyMultiplier = 1.2
      } else if (state === 'processing') {
        baseAmplitude = 4
        baseSpeedMultiplier = 3.0
        baseFrequencyMultiplier = 2.5 // Tighter, faster ripples for thinking
      } else if (state === 'speaking') {
        // Amplitude scales directly with speech playback volume, flat if quiet
        baseAmplitude = audioLevel * 60
        baseSpeedMultiplier = 1.2 + audioLevel * 4
        baseFrequencyMultiplier = 1.0
      } else if (state === 'executing') {
        baseAmplitude = 3
        baseSpeedMultiplier = 1.0
        baseFrequencyMultiplier = 1.0
      } else {
        // Idle / Silent: perfectly flat line
        baseAmplitude = 0
        baseSpeedMultiplier = 0.1
        baseFrequencyMultiplier = 0.5
      }

      // Draw each wave
      waves.forEach((wave) => {
        ctx.beginPath()

        // Slowly update phase based on state speed
        wave.phase += wave.speed * baseSpeedMultiplier

        const amp = wave.amplitude * baseAmplitude
        const freq = wave.frequency * baseFrequencyMultiplier

        // Thinner and more transparent baseline when idle
        const isIdle = baseAmplitude === 0
        ctx.strokeStyle = `rgba(${wave.color}, ${isIdle ? 0.25 : wave.alpha})`
        ctx.lineWidth = isIdle ? 1.0 : 2.5
        ctx.shadowBlur = isIdle ? 2 : 12
        ctx.shadowColor = `rgba(${wave.color}, 0.5)`

        for (let x = 0; x < width; x++) {
          // Siri-style organic tapering: make waves smaller at the edges
          const edgeTaper = Math.sin((x / width) * Math.PI)
          
          // Generate wave height
          const y =
            height / 2 +
            Math.sin(x * freq + wave.phase) * amp * edgeTaper +
            Math.cos(x * (freq * 0.5) - wave.phase * 0.7) * (amp * 0.3) * edgeTaper

          if (x === 0) {
            ctx.moveTo(x, y)
          } else {
            ctx.lineTo(x, y)
          }
        }

        ctx.stroke()
      })

      ctx.shadowBlur = 0 // Reset shadow blur

      // Add a subtle ready notification message directly below the wave in idle state
      if (state === 'wake_word_detected') {
        ctx.font = '10px "Inter", sans-serif'
        ctx.fillStyle = 'rgba(0, 229, 255, 0.8)'
        ctx.textAlign = 'center'
        ctx.fillText('JARVIS ACTIVATED', width / 2, height - 12)
      } else if (state === 'listening') {
        ctx.font = '10px "Inter", sans-serif'
        ctx.fillStyle = 'rgba(0, 229, 255, 0.8)'
        ctx.textAlign = 'center'
        ctx.fillText('LISTENING...', width / 2, height - 12)
      }

      animationFrameId = requestAnimationFrame(render)
    }

    render()

    return () => {
      window.removeEventListener('resize', resizeCanvas)
      cancelAnimationFrame(animationFrameId)
    }
  }, [state, audioLevel])

  return (
    <div className="w-full h-full flex flex-col items-center justify-center p-2 rounded-2xl border border-white/10 bg-black/30 backdrop-blur-2xl relative overflow-hidden shadow-[inset_0_1px_1px_rgba(255,255,255,0.2),0_8px_32px_rgba(0,0,0,0.4)] select-none">
      {/* Siri glow spot in the center background */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-48 h-12 rounded-full bg-jarvis-accent/10 blur-2xl pointer-events-none" />

      {/* Decorative top dot simulating camera/sensor bezel slot */}
      <div className="w-16 h-1 rounded-full bg-white/10 mb-1" />

      {/* Main visual canvas */}
      <div className="w-full flex-1 relative min-h-[50px]">
        <canvas ref={canvasRef} className="w-full h-full absolute inset-0" />
      </div>
      
      {/* Tiny listening cue dots */}
      <div className="flex gap-1.5 mb-1">
        <span className={`w-1 h-1 rounded-full transition-all duration-300 ${state === 'listening' ? 'bg-jarvis-accent scale-125' : 'bg-white/20'}`} />
        <span className={`w-1 h-1 rounded-full transition-all duration-300 ${state === 'processing' ? 'bg-jarvis-accent-2 scale-125 animate-bounce' : 'bg-white/20'}`} />
        <span className={`w-1 h-1 rounded-full transition-all duration-300 ${state === 'speaking' ? 'bg-jarvis-accent-3 scale-125' : 'bg-white/20'}`} />
      </div>
    </div>
  )
}

export default SiriWidget
