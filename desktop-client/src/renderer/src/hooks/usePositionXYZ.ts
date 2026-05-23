import { useState, useEffect } from 'react'
import type { MachineStatus } from '../types/api'

export interface UsePositionXYZResult {
  position: { x: number; y: number; z: number } | null
  homed: string[]
  error: string | null
  stale: boolean
  loading: boolean
}

export function usePositionXYZ(): UsePositionXYZResult {
  const [position, setPosition] = useState<{ x: number; y: number; z: number } | null>(null)
  const [homed, setHomed] = useState<string[]>([])
  const [error, setError] = useState<string | null>(null)
  const [stale, setStale] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let mounted = true
    let intervalId: ReturnType<typeof setInterval> | null = null
    let visibilityTimer: ReturnType<typeof setTimeout> | null = null
    let inflight = false
    let failCount = 0

    async function fetchPosition(): Promise<void> {
      if (!mounted || inflight) return
      inflight = true
      try {
        const result = await window.electronAPI.getMachineStatus()
        if (!mounted) return
        const status = result as MachineStatus
        setPosition(status.position ?? null)
        setHomed(status.homed ?? [])
        setError(null)
        failCount = 0
        setStale(false)
        setLoading(false)
      } catch (err) {
        if (!mounted) return
        failCount++
        setError(err instanceof Error ? err.message : 'Unknown error')
        if (failCount >= 2) setStale(true)
        setLoading(false)
      } finally {
        inflight = false
      }
    }

    function clearPoll(): void {
      if (intervalId !== null) { clearInterval(intervalId); intervalId = null }
    }

    function startPoll(): void {
      clearPoll()
      void fetchPosition()
      intervalId = setInterval(() => { void fetchPosition() }, 2000)
    }

    function onVisibilityChange(): void {
      if (visibilityTimer !== null) clearTimeout(visibilityTimer)
      visibilityTimer = setTimeout(() => {
        visibilityTimer = null
        if (document.hidden) { clearPoll() } else { startPoll() }
      }, 150)
    }

    if (!document.hidden) {
      startPoll()
    }

    document.addEventListener('visibilitychange', onVisibilityChange)

    return () => {
      mounted = false
      clearPoll()
      if (visibilityTimer !== null) clearTimeout(visibilityTimer)
      document.removeEventListener('visibilitychange', onVisibilityChange)
    }
  }, [])

  return { position, homed, error, stale, loading }
}
