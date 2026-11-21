import { useState } from 'react'
import { useMachineData } from '../../context/MachineDataContext'
import { useRole } from '../../context/RoleContext'

const STEPS_MM = [0.1, 1, 10]
const MAIN_AXES = ['X', 'Y', 'Z']
const EXTRA_AXES = ['A', 'B', 'C']
const DEFAULT_SPEED = 600
const MAX_SPEED = 5000

type Message = { kind: 'ok' | 'error'; text: string }

// Electron wraps main-process errors: "Error invoking remote method 'x': Error: <detail>".
function cleanError(err: unknown): string {
  const raw = err instanceof Error ? err.message : String(err)
  return raw.replace(/^Error invoking remote method '[^']+': (Error: )?/, '')
}

export function JogControlPanel(): JSX.Element {
  const { data, stale } = useMachineData()
  const isMachine = useRole() === 'machine'
  const state = data?.state ?? 'UNAVAILABLE'

  const [step, setStep] = useState(1)
  const [speedText, setSpeedText] = useState(String(DEFAULT_SPEED))
  const [showExtra, setShowExtra] = useState(false)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<Message | null>(null)

  const speed = Number(speedText)
  const speedValid = Number.isFinite(speed) && speed > 0 && speed <= MAX_SPEED

  // Motion only when the status is fresh and the machine is idle and powered.
  const canMove = isMachine && state === 'IDLE' && !stale && !busy
  const canJog = canMove && speedValid

  async function run(label: string, action: () => Promise<unknown>): Promise<void> {
    setBusy(true)
    try {
      await action()
      setMessage({ kind: 'ok', text: label })
    } catch (err) {
      setMessage({ kind: 'error', text: cleanError(err) })
    } finally {
      setBusy(false)
    }
  }

  // Stopping must never wait for another command to finish, so it ignores `busy`.
  async function stop(): Promise<void> {
    try {
      await window.electronAPI.setEstop(true)
      setMessage({ kind: 'ok', text: 'E-stop enviado' })
    } catch (err) {
      setMessage({ kind: 'error', text: cleanError(err) })
    }
  }

  function jogButtons(axes: string[]): JSX.Element[] {
    return axes.map(axis => (
      <div key={axis} className="jog-axis">
        <span className="jog-axis-label">{axis}</span>
        <button
          className="jog-btn"
          aria-label={`Jog ${axis}-`}
          disabled={!canJog}
          onClick={() => void run(`${axis} -${step} mm`, () =>
            window.electronAPI.jog({ axis, distance: -step, speed }))}
        >
          −
        </button>
        <button
          className="jog-btn"
          aria-label={`Jog ${axis}+`}
          disabled={!canJog}
          onClick={() => void run(`${axis} +${step} mm`, () =>
            window.electronAPI.jog({ axis, distance: step, speed }))}
        >
          +
        </button>
      </div>
    ))
  }

  return (
    <div className="jog-panel">
      <div className="jog-state">
        <span>Estado:</span>
        <span className={`diag-badge diag-badge--${state === 'ESTOP' ? 'error' : state === 'IDLE' ? 'ok' : 'off'}`}>
          {state}
        </span>
        {stale && <span className="jog-message">estado desactualizado</span>}
      </div>

      <div className="jog-actions">
        <button className="jog-btn jog-btn--stop" onClick={() => void stop()}>
          E-STOP
        </button>
        <button
          className="jog-btn"
          disabled={!isMachine || state !== 'ESTOP' || stale || busy}
          onClick={() => void run('Rearme enviado', () => window.electronAPI.setEstop(false))}
        >
          Rearmar E-stop
        </button>
        <button
          className="jog-btn"
          disabled={!isMachine || state !== 'OFF' || stale || busy}
          onClick={() => void run('Máquina encendida', () => window.electronAPI.setPower(true))}
        >
          Machine ON
        </button>
        <button
          className="jog-btn"
          disabled={!canMove}
          onClick={() => void run('Máquina apagada', () => window.electronAPI.setPower(false))}
        >
          Machine OFF
        </button>
        <button
          className="jog-btn"
          disabled={!canMove}
          onClick={() => void run('Homing iniciado', () => window.electronAPI.homeAll())}
        >
          Home
        </button>
      </div>

      <div className="jog-steps">
        <span>Paso (mm):</span>
        {STEPS_MM.map(value => (
          <button
            key={value}
            className={`jog-btn${step === value ? ' jog-btn--active' : ''}`}
            aria-pressed={step === value}
            onClick={() => setStep(value)}
          >
            {value}
          </button>
        ))}
        <label className="jog-speed">
          Velocidad (mm/min)
          <input
            type="number"
            min={1}
            max={MAX_SPEED}
            value={speedText}
            onChange={e => setSpeedText(e.target.value)}
            aria-invalid={!speedValid}
          />
        </label>
      </div>

      {jogButtons(MAIN_AXES)}

      <label className="io-toggle">
        <input
          type="checkbox"
          checked={showExtra}
          onChange={e => setShowExtra(e.target.checked)}
        />
        Ejes extra (A, B, C)
      </label>
      {showExtra && jogButtons(EXTRA_AXES)}

      {message && (
        <div
          role={message.kind === 'error' ? 'alert' : 'status'}
          className={message.kind === 'error' ? 'diag-error' : 'jog-message'}
        >
          {message.text}
        </div>
      )}
    </div>
  )
}
