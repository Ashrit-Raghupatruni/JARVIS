import React, { useRef, useEffect, useCallback } from 'react'
import { useAppStore } from '../stores/appStore'

interface VoiceWaveProps {
  barCount?: number
  barWidth?: number
  barGap?: number
  height?: number
  mode?: 'input' | 'output'
}

const VoiceWave: React.FC<VoiceWaveProps> = ({
  barCount = 40,
  barWidth = 3,
  barGap = 2,
  height = 60,
  mode = 'input'
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const animFrameRef = useRef<number | null>(null)
  const barsRef = useRef<number[]>(new Array(barCount).fill(0))
  const targetBarsRef = useRef<number[]>(new Array(barCount).fill(0))

  const audioLevel = useAppStore((s) => s.audioLevel)
  const isListening = useAppStore((s) => s.isListening)
  const isSpeaking = useAppStore((s) => s.isSpeaking)

  const isActive = mode === 'input' ? isListening : isSpeaking

  const canvasWidth = barCount * (barWidth + barGap) - barGap

  const draw = useCallback(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const dpr = window.devicePixelRatio || 1
    canvas.width = canvasWidth * dpr
    canvas.height = height * dpr
    ctx.scale(dpr, dpr)

    ctx.clearRect(0, 0, canvasWidth, height)

    const level = isActive ? audioLevel : 0
    const centerIndex = Math.floor(barCount / 2)

    // Generate target bar heights
    for (let i = 0; i < barCount; i++) {
      const distFromCenter = Math.abs(i - centerIndex) / centerIndex
      const envelope = 1 - distFromCenter * 0.7

      if (isActive && level > 0.01) {
        const noise = Math.sin(Date.now() * 0.008 + i * 0.5) * 0.3 +
          Math.sin(Date.now() * 0.012 + i * 1.2) * 0.2 +
          Math.sin(Date.now() * 0.005 + i * 0.3) * 0.15
        const randomness = 0.5 + noise * 0.5
        targetBarsRef.current[i] = level * envelope * randomness * height * 0.85
      } else {
        // Idle: tiny ambient ripple
        const ambient = Math.sin(Date.now() * 0.002 + i * 0.4) * 0.5 + 0.5
        targetBarsRef.current[i] = ambient * 2
      }
    }

    // Smooth interpolation
    for (let i = 0; i < barCount; i++) {
      const lerp = isActive ? 0.25 : 0.1
      barsRef.current[i] += (targetBarsRef.current[i] - barsRef.current[i]) * lerp
    }

    // Draw bars
    for (let i = 0; i < barCount; i++) {
      const x = i * (barWidth + barGap)
      const barHeight = Math.max(2, barsRef.current[i])
      const y = (height - barHeight) / 2

      // Gradient per bar
      const gradient = ctx.createLinearGradient(x, y, x, y + barHeight)

      if (mode === 'input') {
        gradient.addColorStop(0, `rgba(0, 229, 255, ${0.3 + level * 0.5})`)
        gradient.addColorStop(0.5, `rgba(0, 174, 255, ${0.6 + level * 0.4})`)
        gradient.addColorStop(1, `rgba(0, 229, 255, ${0.3 + level * 0.3})`)
      } else {
        gradient.addColorStop(0, `rgba(0, 174, 255, ${0.3 + level * 0.5})`)
        gradient.addColorStop(0.5, `rgba(213, 0, 249, ${0.5 + level * 0.4})`)
        gradient.addColorStop(1, `rgba(0, 229, 255, ${0.3 + level * 0.3})`)
      }

      ctx.fillStyle = gradient
      ctx.beginPath()
      ctx.roundRect(x, y, barWidth, barHeight, barWidth / 2)
      ctx.fill()

      // Glow effect for active bars
      if (barHeight > 10 && isActive) {
        ctx.shadowColor = 'rgba(0, 229, 255, 0.4)'
        ctx.shadowBlur = 6
        ctx.fillStyle = `rgba(0, 229, 255, ${0.1 + level * 0.15})`
        ctx.beginPath()
        ctx.roundRect(x, y, barWidth, barHeight, barWidth / 2)
        ctx.fill()
        ctx.shadowBlur = 0
      }
    }

    animFrameRef.current = requestAnimationFrame(draw)
  }, [audioLevel, barCount, barGap, barWidth, canvasWidth, height, isActive, mode])

  useEffect(() => {
    animFrameRef.current = requestAnimationFrame(draw)

    return () => {
      if (animFrameRef.current) {
        cancelAnimationFrame(animFrameRef.current)
      }
    }
  }, [draw])

  return (
    <div
      className="flex items-center justify-center transition-opacity duration-500"
      style={{ opacity: isActive ? 1 : 0.3 }}
    >
      <canvas
        ref={canvasRef}
        style={{
          width: canvasWidth,
          height,
          imageRendering: 'auto'
        }}
      />
    </div>
  )
}

export default VoiceWave
