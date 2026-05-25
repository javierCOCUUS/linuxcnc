import { usePositionXYZ } from '../../hooks/usePositionXYZ'

const AXES = ['X', 'Y', 'Z'] as const

export function PositionXYZPanel(): JSX.Element {
  const { position, homed, error, stale, loading } = usePositionXYZ()

  if (loading && !position && !error) {
    return (
      <div className="position-xyz-panel">
        {AXES.map(axis => (
          <div key={axis} className="pos-row">
            <span className="pos-axis">{axis}</span>
            <span className="pos-value">—</span>
            <span className="pos-homed-dot" style={{ background: '#444' }} />
          </div>
        ))}
      </div>
    )
  }

  if (!position && error) {
    return (
      <div className="position-xyz-panel">
        <div className="pos-error" role="alert">{error}</div>
      </div>
    )
  }

  const values: Record<string, number> = {
    X: position?.x ?? 0,
    Y: position?.y ?? 0,
    Z: position?.z ?? 0,
  }

  return (
    <div className="position-xyz-panel">
      {AXES.map(axis => {
        const isHomed = homed.includes(axis)
        return (
          <div key={axis} className="pos-row">
            <span className="pos-axis">{axis}</span>
            <span className="pos-value" style={{ opacity: stale ? 0.5 : 1 }}>
              {values[axis].toFixed(3)}
            </span>
            <span
              className="pos-homed-dot"
              style={{ background: isHomed ? '#22c55e' : '#444' }}
              title={isHomed ? `${axis} homed` : `${axis} not homed`}
            />
          </div>
        )
      })}
      {stale && <div className="pos-stale">stale</div>}
      {position && error && <div className="pos-error" role="alert">{error}</div>}
    </div>
  )
}
