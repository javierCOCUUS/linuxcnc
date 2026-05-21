import { useState, useEffect } from 'react'
import type { MachineStatus } from '../types/api'

interface StatusState {
  status: MachineStatus | null
  error: string | null
}

export function useMachineStatus(intervalMs = 2000): StatusState {
  const [state, setState] = useState<StatusState>({ status: null, error: null })

  useEffect(() => {
    let cancelled = false

    async function poll(): Promise<void> {
      try {
        const status = await window.electronAPI.getMachineStatus()
        if (!cancelled) setState({ status, error: null })
      } catch (err) {
        if (!cancelled) setState(prev => ({ ...prev, error: String(err) }))
      }
    }

    poll()
    const id = setInterval(poll, intervalMs)
    return () => {
      cancelled = true
      clearInterval(id)
    }
  }, [intervalMs])

  return state
}
