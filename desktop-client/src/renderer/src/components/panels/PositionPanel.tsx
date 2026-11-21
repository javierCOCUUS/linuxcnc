import { useState } from 'react'
import { useMachineData } from '../../context/MachineDataContext'
import { useRole } from '../../context/RoleContext'
import { cleanError } from '../../lib/errors'
import { PositionXYZPanel } from './PositionXYZPanel'

// Position readout plus the actions that go with it: work zero, go to zero, park and home.
export function PositionPanel(): JSX.Element {
  const { data, stale } = useMachineData()
  const isMachine = useRole() === 'machine'
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const can = isMachine && data?.state === 'IDLE' && !stale && !busy

  async function run(action: () => Promise<unknown>): Promise<void> {
    setBusy(true)
    try {
      await action()
      setError(null)
    } catch (err) {
      setError(cleanError(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="position-card">
      <PositionXYZPanel />
      <div className="position-actions">
        {(['X', 'Y', 'Z'] as const).map(axis => (
          <button
            key={axis}
            className="jog-btn"
            disabled={!can}
            onClick={() => void run(() => window.electronAPI.positionCommand({ action: 'zero', axis }))}
          >
            {axis} = 0
          </button>
        ))}
        <button className="jog-btn" disabled={!can} onClick={() => void run(() => window.electronAPI.positionCommand({ action: 'goto-zero' }))}>
          GO TO ZERO
        </button>
        <button className="jog-btn" disabled={!can} onClick={() => void run(() => window.electronAPI.positionCommand({ action: 'park' }))}>
          IR A PARK
        </button>
        <button className="jog-btn" disabled={!can} onClick={() => void run(() => window.electronAPI.homeAll())}>
          REF ALL HOME
        </button>
      </div>
      {error && <div role="alert" className="diag-error">{error}</div>}
    </div>
  )
}
