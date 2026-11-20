import { useState, useEffect } from 'react'
import { parseHalInputs } from '../lib/halInputs'
import type { HalInput } from '../lib/halInputs'

const POLL_MS = 500

export interface UseHalInputsResult {
  inputs: HalInput[]
  error: string | null
  loading: boolean
}

export function useHalInputs(): UseHalInputsResult {
  const [inputs, setInputs] = useState<HalInput[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let intervalId: ReturnType<typeof setInterval> | null = null
    let visibilityTimer: ReturnType<typeof setTimeout> | null = null
    let mounted = true
    let inflight = false

    async function fetchInputs(): Promise<void> {
      if (!mounted || inflight) return
      inflight = true
      try {
        const pins = await window.electronAPI.getHalInputs()
        if (!mounted) return
        setInputs(parseHalInputs(pins))
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
      void fetchInputs()
      intervalId = setInterval(() => { void fetchInputs() }, POLL_MS)
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

  return { inputs, error, loading }
}
