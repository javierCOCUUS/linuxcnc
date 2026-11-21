import { useState } from 'react'
import { useMachineData } from '../../context/MachineDataContext'

const MAX_RPM = 24000
const PRESETS = [6000, 12000, 18000, 24000]

type Ordered = { state: 'on' | 'reverse' | 'off'; rpm: number }
type Message = { kind: 'ok' | 'error'; text: string }

function cleanError(err: unknown): string {
  const raw = err instanceof Error ? err.message : String(err)
  return raw.replace(/^Error invoking remote method '[^']+': (Error: )?/, '')
}

function describe(ordered: Ordered): string {
  if (ordered.state === 'off') return 'M5 (parado)'
  return `${ordered.state === 'reverse' ? 'M4' : 'M3'} S${ordered.rpm}`
}

export function SpindlePanel(): JSX.Element {
  const { data, stale } = useMachineData()
  const machine = data?.state ?? 'UNAVAILABLE'

  const [rpmText, setRpmText] = useState('12000')
  const [ordered, setOrdered] = useState<Ordered | null>(null)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<Message | null>(null)

  const rpm = Number(rpmText)
  const rpmValid = Number.isInteger(rpm) && rpm > 0 && rpm <= MAX_RPM
  const canCommand = (machine === 'IDLE' || machine === 'MDI') && !stale && !busy
  const running = ordered !== null && ordered.state !== 'off'

  async function command(state: Ordered['state']): Promise<void> {
    const next: Ordered = { state, rpm: state === 'off' ? 0 : rpm }
    setBusy(true)
    try {
      await window.electronAPI.setSpindle({ state, rpm: next.rpm })
      setOrdered(next)
      setMessage({ kind: 'ok', text: describe(next) })
    } catch (err) {
      setMessage({ kind: 'error', text: cleanError(err) })
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="spindle-panel">
      <div className="spindle-readout">
        <span className="spindle-rpm">{rpmValid ? rpm : '—'}</span>
        <span className="spindle-unit">rpm</span>
        <span className={`diag-badge diag-badge--${running ? 'ok' : 'off'}`}>
          {ordered === null ? 'SIN ORDEN' : ordered.state === 'off' ? 'PARADO' : ordered.state === 'reverse' ? 'REV' : 'ON'}
        </span>
      </div>

      <input
        type="range"
        className="spindle-slider"
        aria-label="Velocidad del spindle"
        min={0}
        max={MAX_RPM}
        step={100}
        value={rpmValid ? rpm : 0}
        onChange={e => setRpmText(e.target.value)}
      />

      <div className="spindle-presets">
        {PRESETS.map(value => (
          <button
            key={value}
            className={`jog-btn${rpm === value ? ' jog-btn--active' : ''}`}
            aria-pressed={rpm === value}
            onClick={() => setRpmText(String(value))}
          >
            {value}
          </button>
        ))}
        <label className="jog-speed">
          rpm
          <input
            type="number"
            min={1}
            max={MAX_RPM}
            value={rpmText}
            onChange={e => setRpmText(e.target.value)}
            aria-label="rpm"
            aria-invalid={!rpmValid}
          />
        </label>
      </div>

      <div className="spindle-actions">
        <button className="jog-btn jog-btn--go" disabled={!canCommand || !rpmValid} onClick={() => void command('on')}>
          ON (M3)
        </button>
        <button className="jog-btn" disabled={!canCommand || !rpmValid} onClick={() => void command('reverse')}>
          REV (M4)
        </button>
        <button className="jog-btn jog-btn--stop" disabled={!canCommand} onClick={() => void command('off')}>
          OFF (M5)
        </button>
        {running && (
          <button
            className="jog-btn"
            disabled={!canCommand || !rpmValid || rpm === ordered!.rpm}
            onClick={() => void command(ordered!.state)}
          >
            Aplicar rpm
          </button>
        )}
      </div>

      {ordered && <div className="jog-message">Ordenado: {describe(ordered)}</div>}
      {message?.kind === 'error' && (
        <div role="alert" className="diag-error">{message.text}</div>
      )}
    </div>
  )
}
