import { useState, useEffect } from 'react'
import type { MachineStatus } from '../types/api'

export interface UseMachineStatusResult {
  data: MachineStatus | null
  error: string | null
  stale: boolean
  loading: boolean
}

export function useMachineStatus(): UseMachineStatusResult {
  const [data, setData] = useState<MachineStatus | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [stale, setStale] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let intervalId: ReturnType<typeof setInterval> | null = null
    let mounted = true
    let failCount = 0

    async function fetchStatus(): Promise<void> {
      if (!mounted) return
      try {
        const result = await window.electronAPI.getMachineStatus()
        if (!mounted) return
        setData(result as MachineStatus)
        setError(null)
        failCount = 0
        setStale(false)
        setLoading(false)
      } catch (err) {
        if (!mounted) return
        failCount += 1
        setError(err instanceof Error ? err.message : 'Unknown error')
        if (failCount >= 2) setStale(true)
        setLoading(false)
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
      void fetchStatus()
      intervalId = setInterval(() => { void fetchStatus() }, 2000)
    }

    function onVisibilityChange(): void {
      if (document.hidden) { clearPoll() } else { startPoll() }
    }

    function onFocus(): void { startPoll() }
    function onBlur(): void { clearPoll() }

    if (!document.hidden) {
      startPoll()
    }

    document.addEventListener('visibilitychange', onVisibilityChange)
    window.addEventListener('focus', onFocus)
    window.addEventListener('blur', onBlur)

    return () => {
      mounted = false
      clearPoll()
      document.removeEventListener('visibilitychange', onVisibilityChange)
      window.removeEventListener('focus', onFocus)
      window.removeEventListener('blur', onBlur)
    }
  }, [])

  return { data, error, stale, loading }
}
