import { useMachineStatus } from '../../hooks/useMachineStatus'

const STATE_COLORS: Record<string, string> = {
  IDLE:        '#22c55e',
  RUNNING:     '#00aaff',
  OFF:         '#666',
  PAUSED:      '#f59e0b',
  MDI:         '#a855f7',
  ESTOP:       '#ff4444',
  UNAVAILABLE: '#666',
}

export function MachineStatusPanel(): JSX.Element {
  const { data, error, stale, loading } = useMachineStatus()

  if (loading && !data && !error) {
    return (
      <div className="machine-status-panel">
        <div className="ms-state-badge" style={{ color: '#666' }}>—</div>
        <div className="ms-row"><span className="ms-label">Spindle</span><span>—</span></div>
        <div className="ms-row"><span className="ms-label">Feed</span><span>—</span></div>
        <div className="ms-row"><span className="ms-label">Homed</span><span>—</span></div>
        <div className="ms-row"><span className="ms-label">G-code</span><span>—</span></div>
      </div>
    )
  }

  if (!data && error) {
    return (
      <div className="machine-status-panel">
        <div className="ms-error" role="alert">{error}</div>
      </div>
    )
  }

  const stateText = stale ? `${data?.state ?? '—'} (stale)` : (data?.state ?? '—')
  const stateColor = STATE_COLORS[data?.state ?? ''] ?? '#666'
  const stateOpacity = stale ? 0.5 : 1

  const spindleOn = data?.spindle?.on
  const spindleText = spindleOn
    ? `ON  ${data?.spindle?.speed ?? 0} rpm  ${data?.spindle?.direction ?? ''}`
    : 'OFF'

  const feedText = data?.feed_rate != null ? `${data.feed_rate}%` : '—'
  const homedText = (data?.homed?.length ?? 0) > 0
    ? (data?.homed ?? []).join(' ')
    : 'None'
  const gcodeText = data?.active_gcode ?? '—'
  const backendText = data?.system?.backend ?? ''
  const systemError = data?.system?.error

  return (
    <div className="machine-status-panel">
      <div className="ms-header">
        <span
          className="ms-state-badge"
          style={{ color: stateColor, opacity: stateOpacity }}
        >
          {stateText}
        </span>
        {backendText && <span className="ms-backend">{backendText}</span>}
      </div>
      <div className="ms-row">
        <span className="ms-label">Spindle</span>
        <span>{spindleText}</span>
      </div>
      <div className="ms-row">
        <span className="ms-label">Feed</span>
        <span>{feedText}</span>
      </div>
      <div className="ms-row">
        <span className="ms-label">Homed</span>
        <span>{homedText}</span>
      </div>
      <div className="ms-row">
        <span className="ms-label">G-code</span>
        <span>{gcodeText}</span>
      </div>
      {systemError && (
        <div className="ms-error" role="alert">{systemError}</div>
      )}
    </div>
  )
}
