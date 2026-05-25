import { useMachineStatus } from '../hooks/useMachineStatus'

export function StatusBar(): JSX.Element {
  const { status, error } = useMachineStatus()

  if (error) {
    return <div className="status-bar status-bar--error">⚠ {error}</div>
  }
  if (!status) {
    return <div className="status-bar status-bar--connecting">Connecting...</div>
  }

  return (
    <div className={`status-bar status-bar--${status.state.toLowerCase()}`}>
      <span className="status-state">{status.state}</span>
      <span>X:{status.position.x.toFixed(3)}</span>
      <span>Y:{status.position.y.toFixed(3)}</span>
      <span>Z:{status.position.z.toFixed(3)}</span>
      <span>T:{status.tool}</span>
      <span>{status.units}</span>
    </div>
  )
}
