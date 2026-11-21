import { useState } from 'react'
import { useHalInputs } from '../../hooks/useHalInputs'
import type { HalInput } from '../../lib/halInputs'

function InputRow({ input }: { input: HalInput }): JSX.Element {
  return (
    <div className="io-row" data-testid={`io-row-${input.id}`}>
      <span className="io-label">IN {input.id}</span>
      <span className={`diag-badge diag-badge--${input.on ? 'ok' : 'off'}`}>
        {input.on ? 'ON' : 'OFF'}
      </span>
      {input.signal ? (
        <span className="io-signal">
          {'→ '}{input.signal}
          {input.inverted ? ' (inv)' : ''}
          {': '}{input.signalOn ? 'TRUE' : 'FALSE'}
        </span>
      ) : (
        <span className="io-signal io-signal--none">sin señal</span>
      )}
    </div>
  )
}

export function IoInputsPanel(): JSX.Element {
  const { inputs, error, loading } = useHalInputs()
  const [onlyWired, setOnlyWired] = useState(true)

  if (loading && inputs.length === 0) {
    return <div className="io-panel"><span className="io-signal">Cargando entradas…</span></div>
  }

  if (error && inputs.length === 0) {
    return (
      <div className="io-panel">
        <div role="alert" className="diag-error">{error}</div>
      </div>
    )
  }

  if (inputs.length === 0) {
    return <div className="io-panel"><span className="io-signal">No hay entradas</span></div>
  }

  const visible = onlyWired ? inputs.filter(input => input.signal !== null) : inputs

  return (
    <div className="io-panel">
      <label className="io-toggle">
        <input
          type="checkbox"
          checked={onlyWired}
          onChange={e => setOnlyWired(e.target.checked)}
        />
        Solo con señal
      </label>
      {error && <div role="alert" className="diag-error">{error}</div>}
      {visible.length === 0 && (
        <span className="io-signal">Ninguna entrada tiene señal conectada</span>
      )}
      {visible.map(input => <InputRow key={input.id} input={input} />)}
    </div>
  )
}
