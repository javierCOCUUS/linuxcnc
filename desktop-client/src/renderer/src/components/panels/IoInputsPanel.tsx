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

  return (
    <div className="io-panel">
      {error && <div role="alert" className="diag-error">{error}</div>}
      {inputs.map(input => <InputRow key={input.id} input={input} />)}
    </div>
  )
}
