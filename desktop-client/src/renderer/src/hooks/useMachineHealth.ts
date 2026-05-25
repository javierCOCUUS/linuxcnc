import { useState, useEffect } from 'react'
import type { MachineHealth } from '../types/api'

export interface UseMachineHealthResult {
  data: MachineHealth | null
  error: string | null
  loading: boolean
}

export function useMachineHealth(): UseMachineHealthResult {
  const [data, setData] = useState<MachineHealth | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let intervalId: ReturnType<typeof setInterval> | null = null
    let visibilityTimer: ReturnType<typeof setTimeout> | null = null
    let mounted = true
    let inflight = false

    async function fetchHealth(): Promise<void> {
      if (!mounted || inflight) return
      inflight = true
      try {
        const result = await window.electronAPI.getMachineHealth()
        if (!mounted) return
        setData(result as MachineHealth)
        setError(null)
        setLoading(false)
      } catch (err) {
        if (!mounted) return
        setError(err instanceof Error ? err.message : 'Unknown error')
        setLoading(false)
      } finally {
        inflight = false
      }
    }

    function clearPoll(): void {
      if (intervalId !== null) {
        clearInterval(intervalId)
        intervalId = null
      }
    }

    function startPoll(): void {
      clearPoll()
      void fetchHealth()
      intervalId = setInterval(() => { void fetchHealth() }, 10_000)
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

  return { data, error, loading }
}
