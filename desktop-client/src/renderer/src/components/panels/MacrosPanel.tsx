import { useState } from 'react'
import { useMachineData } from '../../context/MachineDataContext'
import { useRole } from '../../context/RoleContext'
import { gcodeLines, loadMacros, newMacro, saveMacros } from '../../lib/macros'
import type { Macro } from '../../lib/macros'

type Message = { kind: 'ok' | 'error'; text: string }

function cleanError(err: unknown): string {
  const raw = err instanceof Error ? err.message : String(err)
  return raw.replace(/^Error invoking remote method '[^']+': (Error: )?/, '')
}

export function MacrosPanel(): JSX.Element {
  const { data, stale } = useMachineData()
  const isMachine = useRole() === 'machine'
  const machine = data?.state ?? 'UNAVAILABLE'

  const [macros, setMacros] = useState<Macro[]>(() => loadMacros())
  const [editing, setEditing] = useState(false)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<Message | null>(null)

  const canRun = isMachine && (machine === 'IDLE' || machine === 'MDI') && !stale && !busy

  function update(next: Macro[]): void {
    setMacros(next)
    saveMacros(next)
  }

  function change(id: string, patch: Partial<Macro>): void {
    update(macros.map(m => (m.id === id ? { ...m, ...patch } : m)))
  }

  async function run(macro: Macro): Promise<void> {
    const lines = gcodeLines(macro.gcode)
    if (lines.length === 0) {
      setMessage({ kind: 'error', text: `«${macro.name}» no tiene líneas de G-code` })
      return
    }
    if (macro.confirm && !window.confirm(`¿Ejecutar «${macro.name}»?\n\n${lines.join('\n')}`)) return

    setBusy(true)
    try {
      for (let i = 0; i < lines.length; i++) {
        try {
          await window.electronAPI.sendGcode(lines[i])
        } catch (err) {
          setMessage({ kind: 'error', text: `Línea ${i + 1} (${lines[i]}): ${cleanError(err)}` })
          return
        }
      }
      setMessage({ kind: 'ok', text: `«${macro.name}» ejecutada` })
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="macros-panel">
      <div className="macros-toolbar">
        <button className="jog-btn" aria-pressed={editing} onClick={() => setEditing(e => !e)}>
          {editing ? 'Hecho' : 'Editar'}
        </button>
        {editing && (
          <button className="jog-btn" onClick={() => update([...macros, newMacro()])}>
            Añadir macro
          </button>
        )}
      </div>

      {macros.length === 0 && (
        <div className="jog-message">
          No hay macros. Pulsa «Editar» y «Añadir macro».
        </div>
      )}

      {!editing && (
        <div className="macros-grid">
          {macros.map(macro => (
            <button
              key={macro.id}
              className="jog-btn macro-btn"
              disabled={!canRun}
              onClick={() => void run(macro)}
            >
              {macro.name}
            </button>
          ))}
        </div>
      )}

      {editing && macros.map(macro => (
        <div key={macro.id} className="macro-editor">
          <input
            className="macro-name"
            aria-label="Nombre de la macro"
            value={macro.name}
            onChange={e => change(macro.id, { name: e.target.value })}
          />
          <textarea
            className="macro-gcode"
            aria-label="G-code de la macro"
            rows={4}
            placeholder={'G0 X0 Y0\nG0 Z5'}
            value={macro.gcode}
            onChange={e => change(macro.id, { gcode: e.target.value })}
          />
          <div className="macro-editor-row">
            <label className="io-toggle">
              <input
                type="checkbox"
                checked={macro.confirm}
                onChange={e => change(macro.id, { confirm: e.target.checked })}
              />
              Confirmar antes de ejecutar
            </label>
            <button
              className="jog-btn jog-btn--stop"
              aria-label={`Borrar ${macro.name}`}
              onClick={() => update(macros.filter(m => m.id !== macro.id))}
            >
              Borrar
            </button>
          </div>
        </div>
      ))}

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
