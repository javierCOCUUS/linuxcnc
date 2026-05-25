import { useMachineData } from '../../context/MachineDataContext'

export function DiagnosticPanel(): JSX.Element {
  const { data, error, loading } = useMachineData()

  if (loading && !data) {
    return (
      <div className="diagnostic-panel">
        {['E-stop', 'Machine', 'Mode', 'Program', 'Backend', 'Target'].map(label => (
          <div key={label} className="diag-row">
            <span className="diag-label">{label}</span>
            <span>—</span>
          </div>
        ))}
      </div>
    )
  }

  if (error && !data) {
    return (
      <div className="diagnostic-panel">
        <div role="alert" className="diag-error">{error}</div>
      </div>
    )
  }

  const sys = data?.system ?? {}
  const estop = sys.estop as string | undefined
  const machine = sys.machine as string | undefined
  const mode = sys.mode as string | undefined
  const programStatus = sys.program_status as string | undefined
  const backend = sys.backend as string | undefined
  const target = sys.target as string | undefined
  const raw = (sys.raw as string[] | undefined) ?? []

  return (
    <div className="diagnostic-panel">
      <div className="diag-row">
        <span className="diag-label">E-stop</span>
        <span className={`diag-badge diag-badge--${estop === 'on' ? 'error' : 'ok'}`}>
          {estop ?? '—'}
        </span>
      </div>
      <div className="diag-row">
        <span className="diag-label">Machine</span>
        <span className={`diag-badge diag-badge--${machine === 'on' ? 'ok' : 'off'}`}>
          {machine ?? '—'}
        </span>
      </div>
      <div className="diag-row">
        <span className="diag-label">Mode</span>
        <span>{mode ?? '—'}</span>
      </div>
      <div className="diag-row">
        <span className="diag-label">Program</span>
        <span>{programStatus ?? '—'}</span>
      </div>
      <div className="diag-row">
        <span className="diag-label">Backend</span>
        <span>{backend ?? '—'}</span>
      </div>
      <div className="diag-row">
        <span className="diag-label">Target</span>
        <span>{target ?? '—'}</span>
      </div>
      {raw.length > 0 && (
        <div className="diag-raw">
          {raw.map((line, i) => (
            <div key={i} className="diag-raw-line">{line}</div>
          ))}
        </div>
      )}
    </div>
  )
}
