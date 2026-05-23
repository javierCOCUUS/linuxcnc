import type { MachineDataContextValue } from '../../context/MachineDataContext'
import { useMachineData } from '../../context/MachineDataContext'

export interface Alarm {
  severity: 'error' | 'warn' | 'ok'
  message: string
}

export function deriveAlarms(ctx: MachineDataContextValue): Alarm[] {
  const { data, stale } = ctx
  if (!data) return []

  const alarms: Alarm[] = []
  const sys = data.system

  if ((sys.estop as string) === 'on') {
    alarms.push({ severity: 'error', message: 'E-stop activo' })
  }
  if ((sys.machine as string) === 'off') {
    alarms.push({ severity: 'warn', message: 'Máquina apagada' })
  }
  if (sys.error) {
    alarms.push({ severity: 'error', message: sys.error as string })
  }
  if (stale) {
    alarms.push({ severity: 'warn', message: 'Datos desactualizados' })
  }

  return alarms
}

const SEVERITY_ICON: Record<Alarm['severity'], string> = {
  error: '🔴',
  warn: '🟡',
  ok: '🟢',
}

export function AlarmsPanel(): JSX.Element {
  const ctx = useMachineData()
  const alarms = deriveAlarms(ctx)

  return (
    <div className="alarms-panel">
      {alarms.length === 0 ? (
        <div className="alarm-item alarm-item--ok">
          <span>{SEVERITY_ICON.ok}</span>
          <span>Sistema OK</span>
        </div>
      ) : (
        alarms.map((alarm, i) => (
          <div key={i} className={`alarm-item alarm-item--${alarm.severity}`}>
            <span>{SEVERITY_ICON[alarm.severity]}</span>
            <span>{alarm.message}</span>
          </div>
        ))
      )}
    </div>
  )
}
