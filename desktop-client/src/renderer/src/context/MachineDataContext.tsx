import { createContext, useContext, useState, useEffect } from 'react'
import type { ReactNode } from 'react'
import type { MachineStatus } from '../types/api'

export interface MachineDataContextValue {
  data: MachineStatus | null
  error: string | null
  stale: boolean
  loading: boolean
}

const MachineDataContext = createContext<MachineDataContextValue>({
  data: null,
  error: null,
  stale: false,
  loading: true,
})

export function MachineDataProvider({ children }: { children: ReactNode }): JSX.Element {
  const [data, setData] = useState<MachineStatus | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [stale, setStale] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let intervalId: ReturnType<typeof setInterval> | null = null
    let visibilityTimer: ReturnType<typeof setTimeout> | null = null
    let mounted = true
    let inflight = false
    let failCount = 0

    async function fetchStatus(): Promise<void> {
      if (!mounted || inflight) return
      inflight = true
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
      void fetchStatus()
      intervalId = setInterval(() => { void fetchStatus() }, 2000)
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

  return (
    <MachineDataContext.Provider value={{ data, error, stale, loading }}>
      {children}
    </MachineDataContext.Provider>
  )
}

export function useMachineData(): MachineDataContextValue {
  return useContext(MachineDataContext)
}
