import { useMachineHealth } from '../../hooks/useMachineHealth'
import type { ServiceCheck } from '../../types/api'

function StatusBadge({ status }: { status: string }): JSX.Element {
  const cls = status === 'ok' ? 'svc-badge--ok'
    : status === 'stub'       ? 'svc-badge--stub'
    : status === 'unconfigured' ? 'svc-badge--stub'
    : 'svc-badge--down'
  return <span className={`svc-badge ${cls}`}>{status}</span>
}

function ServiceRow({ name, check }: { name: string; check: ServiceCheck | undefined }): JSX.Element {
  if (!check) {
    return (
      <div className="svc-row">
        <span className="svc-label">{name}</span>
        <span>—</span>
      </div>
    )
  }
  const detail = check.count != null
    ? `${check.latency_ms}ms · ${check.count} pins`
    : `${check.latency_ms}ms`
  return (
    <div className="svc-row">
      <span className="svc-label">{name}</span>
      <StatusBadge status={check.status} />
      {check.status !== 'ok' && check.status !== 'stub' && check.error && (
        <span className="svc-error">{check.error}</span>
      )}
      {check.status === 'ok' && (
        <span className="svc-detail">{detail}</span>
      )}
    </div>
  )
}

export function ServicesPanel(): JSX.Element {
  const { data, error, loading } = useMachineHealth()

  if (loading && !data) {
    return (
      <div className="services-panel">
        {['linuxcncrsh', 'hal_bridge', 'mesa_pins'].map(name => (
          <div key={name} className="svc-row">
            <span className="svc-label">{name}</span>
            <span>—</span>
          </div>
        ))}
      </div>
    )
  }

  if (error && !data) {
    return (
      <div className="services-panel">
        <div role="alert" className="svc-error-banner">{error}</div>
      </div>
    )
  }

  return (
    <div className="services-panel">
      <ServiceRow name="linuxcncrsh" check={data?.linuxcncrsh} />
      <ServiceRow name="hal_bridge"  check={data?.hal_bridge} />
      <ServiceRow name="mesa_pins"   check={data?.mesa_pins} />
    </div>
  )
}
