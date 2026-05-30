import { useRef, useCallback, useState } from 'react'
import { useAppStore } from '../stores/appStore'

interface UseAudioReturn {
  startMicCapture: () => Promise<void>
  stopMicCapture: () => void
  playAudioChunk: (data: ArrayBuffer) => Promise<void>
  stopPlayback: () => void
  getAudioLevel: () => number
  isCapturing: boolean
}

export function useAudio(
  onAudioData?: (data: ArrayBuffer) => void
): UseAudioReturn {
  const streamRef = useRef<MediaStream | null>(null)
  const audioContextRef = useRef<AudioContext | null>(null)
  const analyserRef = useRef<AnalyserNode | null>(null)
  const processorRef = useRef<ScriptProcessorNode | null>(null)
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null)
  const animFrameRef = useRef<number | null>(null)
  const audioLevelRef = useRef(0)

  // Use React state for isCapturing so it triggers re-renders
  const [isCapturing, setIsCapturing] = useState(false)

  // Playback
  const playbackContextRef = useRef<AudioContext | null>(null)
  const playbackQueueRef = useRef<ArrayBuffer[]>([])
  const isPlayingRef = useRef(false)
  const currentSourceRef = useRef<AudioBufferSourceNode | null>(null)

  const setAudioLevel = useAppStore.getState().setAudioLevel

  const getOrCreateAudioContext = useCallback((): AudioContext => {
    if (!audioContextRef.current || audioContextRef.current.state === 'closed') {
      audioContextRef.current = new AudioContext({ sampleRate: 16000 })
    }
    return audioContextRef.current
  }, [])

  const getOrCreatePlaybackContext = useCallback((): AudioContext => {
    if (!playbackContextRef.current || playbackContextRef.current.state === 'closed') {
      playbackContextRef.current = new AudioContext()
    }
    return playbackContextRef.current
  }, [])

  // Monitor audio level continuously
  const monitorLevel = useCallback(() => {
    if (!analyserRef.current) return

    const dataArray = new Uint8Array(analyserRef.current.frequencyBinCount)
    analyserRef.current.getByteFrequencyData(dataArray)

    let sum = 0
    for (let i = 0; i < dataArray.length; i++) {
      sum += dataArray[i]
    }
    const average = sum / dataArray.length / 255
    audioLevelRef.current = average
    setAudioLevel(average)

    animFrameRef.current = requestAnimationFrame(monitorLevel)
  }, [setAudioLevel])

  const startMicCapture = useCallback(async () => {
    // Guard against starting capture if already capturing
    if (streamRef.current) {
      console.log('[Audio] Mic capture already active, skipping')
      return
    }

    try {
      console.log('[Audio] Requesting microphone access...')
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          sampleRate: 16000,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        }
      })

      streamRef.current = stream
      const ctx = getOrCreateAudioContext()

      if (ctx.state === 'suspended') {
        await ctx.resume()
      }

      const source = ctx.createMediaStreamSource(stream)
      sourceRef.current = source

      // Analyser for visualization
      const analyser = ctx.createAnalyser()
      analyser.fftSize = 256
      analyser.smoothingTimeConstant = 0.8
      analyserRef.current = analyser
      source.connect(analyser)

      // ScriptProcessor for capturing raw audio data
      const bufferSize = 4096
      const processor = ctx.createScriptProcessor(bufferSize, 1, 1)
      processorRef.current = processor

      processor.onaudioprocess = (event: AudioProcessingEvent) => {
        const inputData = event.inputBuffer.getChannelData(0)
        // Convert float32 to int16 PCM
        const pcmData = new Int16Array(inputData.length)
        for (let i = 0; i < inputData.length; i++) {
          const s = Math.max(-1, Math.min(1, inputData[i]))
          pcmData[i] = s < 0 ? s * 0x8000 : s * 0x7fff
        }
        onAudioData?.(pcmData.buffer)
      }

      source.connect(processor)
      processor.connect(ctx.destination)

      // Start level monitoring
      monitorLevel()
      setIsCapturing(true)

      console.log('[Audio] Mic capture started successfully')
    } catch (err) {
      console.error('[Audio] Failed to start mic capture:', err)
      setIsCapturing(false)
      throw err
    }
  }, [getOrCreateAudioContext, monitorLevel, onAudioData])

  const stopMicCapture = useCallback(() => {
    // Stop animation frame
    if (animFrameRef.current) {
      cancelAnimationFrame(animFrameRef.current)
      animFrameRef.current = null
    }

    // Disconnect processor
    if (processorRef.current) {
      processorRef.current.disconnect()
      processorRef.current = null
    }

    // Disconnect source
    if (sourceRef.current) {
      sourceRef.current.disconnect()
      sourceRef.current = null
    }

    // Stop stream tracks
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop())
      streamRef.current = null
    }

    // Close audio context
    if (audioContextRef.current && audioContextRef.current.state !== 'closed') {
      audioContextRef.current.close()
      audioContextRef.current = null
    }

    analyserRef.current = null
    audioLevelRef.current = 0
    setAudioLevel(0)
    setIsCapturing(false)

    console.log('[Audio] Mic capture stopped')
  }, [setAudioLevel])

  const playNextChunk = useCallback(async () => {
    if (playbackQueueRef.current.length === 0) {
      isPlayingRef.current = false
      useAppStore.getState().setSpeaking(false)
      return
    }

    isPlayingRef.current = true
    const chunk = playbackQueueRef.current.shift()!
    const ctx = getOrCreatePlaybackContext()

    if (ctx.state === 'suspended') {
      await ctx.resume()
    }

    try {
      const audioBuffer = await ctx.decodeAudioData(chunk.slice(0))
      const source = ctx.createBufferSource()
      source.buffer = audioBuffer
      source.connect(ctx.destination)
      currentSourceRef.current = source

      source.onended = () => {
        currentSourceRef.current = null
        playNextChunk()
      }

      source.start()
    } catch (err) {
      console.error('[Audio] Failed to decode/play audio chunk:', err)
      currentSourceRef.current = null
      playNextChunk()
    }
  }, [getOrCreatePlaybackContext])

  const playAudioChunk = useCallback(
    async (data: ArrayBuffer) => {
      playbackQueueRef.current.push(data)
      useAppStore.getState().setSpeaking(true)

      if (!isPlayingRef.current) {
        await playNextChunk()
      }
    },
    [playNextChunk]
  )

  const stopPlayback = useCallback(() => {
    playbackQueueRef.current = []

    if (currentSourceRef.current) {
      try {
        currentSourceRef.current.stop()
      } catch {
        // May already be stopped
      }
      currentSourceRef.current = null
    }

    isPlayingRef.current = false
    useAppStore.getState().setSpeaking(false)
  }, [])

  const getAudioLevel = useCallback((): number => {
    return audioLevelRef.current
  }, [])

  return {
    startMicCapture,
    stopMicCapture,
    playAudioChunk,
    stopPlayback,
    getAudioLevel,
    isCapturing
  }
}
