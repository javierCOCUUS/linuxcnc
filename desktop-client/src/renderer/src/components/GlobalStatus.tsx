import { useState } from 'react'
import { useMachineData } from '../context/MachineDataContext'

// Always visible in the header, on every tab: machine state and the emergency stop.
export function GlobalStatus(): JSX.Element {
  const { data, stale } = useMachineData()
  const state = data?.state ?? 'UNAVAILABLE'
  const [error, setError] = useState<string | null>(null)

  async function stop(): Promise<void> {
    try {
      await window.electronAPI.setEstop(true)
      setError(null)
    } catch (err) {
      const raw = err instanceof Error ? err.message : String(err)
      setError(raw.replace(/^Error invoking remote method '[^']+': (Error: )?/, ''))
    }
  }

  const tone = state === 'ESTOP' ? 'error' : state === 'IDLE' ? 'ok' : 'off'

  return (
    <div className="global-status">
      <span className={`diag-badge diag-badge--${tone}`} aria-label="Machine state">{state}</span>
      {stale && <span className="global-status-note">sin datos recientes</span>}
      <button className="estop-btn" aria-label="Emergency stop" onClick={() => void stop()}>
        E-STOP
      </button>
      {error && <span role="alert" className="global-status-error">{error}</span>}
    </div>
  )
}
