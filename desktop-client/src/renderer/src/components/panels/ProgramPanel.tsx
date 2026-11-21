import { useEffect, useState } from 'react'
import { useMachineData } from '../../context/MachineDataContext'
import { useRole } from '../../context/RoleContext'
import { cleanError } from '../../lib/errors'
import type { WorkspaceFile } from '../../types/api'

type Message = { kind: 'ok' | 'error'; text: string }

// The workspace also holds folders and other files; only G-code can be loaded as a program.
export const GCODE_FILE = /\.(tap|nc|ngc|gcode|cnc|txt)$/i

// START needs a program that was opened from this panel, so a stale selection never runs.
export function CycleControls({ openedFile }: { openedFile: string | null }): JSX.Element {
  const { data, stale } = useMachineData()
  const isMachine = useRole() === 'machine'
  const state = data?.state ?? 'UNAVAILABLE'
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<Message | null>(null)

  async function send(action: string, label: string): Promise<void> {
    setBusy(true)
    try {
      await window.electronAPI.programCommand({ action })
      setMessage({ kind: 'ok', text: label })
    } catch (err) {
      setMessage({ kind: 'error', text: cleanError(err) })
    } finally {
      setBusy(false)
    }
  }

  function start(): void {
    if (!window.confirm(`¿Iniciar «${openedFile}»?`)) return
    void send('run', 'Programa iniciado')
  }

  const canStart = isMachine && state === 'IDLE' && !stale && !busy && openedFile !== null
  const paused = state === 'PAUSED'
  // Pausing is open to every role; resuming starts motion again, so it is machine-only.
  const canHold = paused ? isMachine && !stale && !busy : state === 'RUNNING' && !stale && !busy

  return (
    <div className="cycle-controls">
      <button className="cycle-btn cycle-btn--start" disabled={!canStart} onClick={start}>
        CYCLE START
      </button>
      <button
        className="cycle-btn cycle-btn--hold"
        disabled={!canHold}
        onClick={() => void send(paused ? 'resume' : 'pause', paused ? 'Reanudado' : 'Pausa')}
      >
        {paused ? 'RESUME' : 'FEED HOLD'}
      </button>
      {/* Stop must always be possible, so it ignores the machine state and `busy`. */}
      <button className="cycle-btn cycle-btn--stop" onClick={() => void send('stop', 'Stop')}>
        STOP
      </button>
      {message && (
        <div role={message.kind === 'error' ? 'alert' : 'status'} className={message.kind === 'error' ? 'diag-error' : 'jog-message'}>
          {message.text}
        </div>
      )}
    </div>
  )
}

interface ProgramPanelProps {
  showCycle?: boolean
  /** Controlled mode: the opened file is owned by the parent, so a separate CycleControls can share it. */
  opened?: string | null
  onOpened?: (name: string) => void
}

export function ProgramPanel({ showCycle = true, opened: openedProp, onOpened }: ProgramPanelProps): JSX.Element {
  const { data, stale } = useMachineData()
  const isMachine = useRole() === 'machine'
  const state = data?.state ?? 'UNAVAILABLE'

  const [files, setFiles] = useState<WorkspaceFile[] | null>(null)
  const [selected, setSelected] = useState('')
  const [localOpened, setLocalOpened] = useState<string | null>(null)
  const opened = openedProp !== undefined ? openedProp : localOpened
  const setOpened = onOpened ?? setLocalOpened
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<Message | null>(null)

  useEffect(() => {
    let mounted = true
    window.electronAPI.listFiles()
      .then(list => { if (mounted) setFiles(list.filter(f => GCODE_FILE.test(f.name))) })
      .catch(err => { if (mounted) { setFiles([]); setMessage({ kind: 'error', text: cleanError(err) }) } })
    return () => { mounted = false }
  }, [])

  const idleOrPaused = state === 'IDLE' || state === 'PAUSED'
  const canLoad = isMachine && state === 'IDLE' && !stale && !busy && selected !== ''
  const canPrepare = isMachine && opened !== null && idleOrPaused && !stale && !busy

  async function run(label: string, action: () => Promise<unknown>, after?: () => void): Promise<void> {
    setBusy(true)
    try {
      await action()
      after?.()
      setMessage({ kind: 'ok', text: label })
    } catch (err) {
      setMessage({ kind: 'error', text: cleanError(err) })
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="program-panel">
      <div className="program-file">
        <select
          className="program-select"
          aria-label="Archivo de G-code"
          value={selected}
          onChange={e => setSelected(e.target.value)}
        >
          <option value="">{files === null ? 'Cargando…' : files.length === 0 ? 'No hay archivos' : 'Elige un archivo'}</option>
          {(files ?? []).map(f => <option key={f.name} value={f.name}>{f.name}</option>)}
        </select>
      </div>
      <div className="program-current">
        {opened ? <>Cargado: <strong>{opened}</strong></> : 'Ningún programa cargado desde esta pantalla'}
      </div>

      <div className="program-actions">
        <button
          className="jog-btn"
          disabled={!canLoad}
          onClick={() => void run(`«${selected}» cargado`, () => window.electronAPI.programCommand({ action: 'open', filename: selected }), () => setOpened(selected))}
        >
          CARGAR
        </button>
        <button
          className="jog-btn"
          disabled={!canPrepare}
          onClick={() => void run('Programa al principio', () => window.electronAPI.programCommand({ action: 'rewind' }))}
        >
          REWIND
        </button>
        <button
          className="jog-btn"
          disabled={!canPrepare}
          onClick={() => void run('Una línea', () => window.electronAPI.programCommand({ action: 'step' }))}
        >
          LÍNEA A LÍNEA
        </button>
      </div>

      {showCycle && <CycleControls openedFile={opened} />}
      {message && (
        <div role={message.kind === 'error' ? 'alert' : 'status'} className={message.kind === 'error' ? 'diag-error' : 'jog-message'}>
          {message.text}
        </div>
      )}
    </div>
  )
}
