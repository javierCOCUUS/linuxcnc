import { useEffect, useRef, useState } from 'react'
import { useMachineData } from '../../context/MachineDataContext'
import { cleanError } from '../../lib/errors'

// LinuxCNC clamps these to its own configured maximums (MAX_FEED_OVERRIDE, MAX_SPINDLE_OVERRIDE).
const FEED = { min: 0, max: 120, step: 5, presets: [50, 100, 120] }
const SPINDLE = { min: 50, max: 120, step: 5, presets: [50, 100, 120] }
const SEND_DELAY_MS = 300

type Kind = 'feed' | 'spindle'

interface OverrideSliderProps {
  kind: Kind
  label: string
  shown: number
  range: typeof FEED
  disabled: boolean
  onChange: (percent: number) => void
}

function OverrideSlider({ kind, label, shown, range, disabled, onChange }: OverrideSliderProps): JSX.Element {
  return (
    <div className="ovr-block">
      <div className="ovr-head">
        <span className="ovr-label">{label}</span>
        <span className="ovr-value" data-testid={`ovr-${kind}-value`}>{shown}%</span>
      </div>
      <input
        type="range"
        className="spindle-slider"
        aria-label={label}
        min={range.min}
        max={range.max}
        step={range.step}
        value={shown}
        disabled={disabled}
        onChange={e => onChange(Number(e.target.value))}
      />
      <div className="spindle-presets">
        {range.presets.map(value => (
          <button
            key={value}
            className={`jog-btn${shown === value ? ' jog-btn--active' : ''}`}
            aria-label={`${label} ${value}%`}
            disabled={disabled}
            onClick={() => onChange(value)}
          >
            {value}%
          </button>
        ))}
      </div>
    </div>
  )
}

// Overrides can only slow the machine down or speed it up within LinuxCNC's limits, and a
// remote operator is allowed to change them, so no role gating here.
export function OverridesPanel(): JSX.Element {
  const { data, stale } = useMachineData()
  const available = data !== null && data.state !== 'UNAVAILABLE' && !stale

  const [feed, setFeed] = useState<number | null>(null)
  const [spindle, setSpindle] = useState(100)
  const [message, setMessage] = useState<string | null>(null)
  const timers = useRef<Partial<Record<Kind, ReturnType<typeof setTimeout>>>>({})

  useEffect(() => () => {
    Object.values(timers.current).forEach(t => t && clearTimeout(t))
  }, [])

  const reported = Math.round(data?.feed_rate ?? 100)
  const feedShown = feed ?? reported

  function schedule(kind: Kind, percent: number): void {
    if (kind === 'feed') setFeed(percent)
    else setSpindle(percent)
    const pending = timers.current[kind]
    if (pending) clearTimeout(pending)
    // Wait for the slider to stop moving instead of sending a command per tick.
    timers.current[kind] = setTimeout(async () => {
      try {
        await window.electronAPI.setOverride({ kind, percent })
        setMessage(null)
      } catch (err) {
        setMessage(cleanError(err))
      }
      if (kind === 'feed') setFeed(null)
    }, SEND_DELAY_MS)
  }

  return (
    <div className="ovr-panel">
      <OverrideSlider kind="feed" label="Avance" shown={feedShown} range={FEED}
        disabled={!available} onChange={p => schedule('feed', p)} />
      <OverrideSlider kind="spindle" label="Spindle" shown={spindle} range={SPINDLE}
        disabled={!available} onChange={p => schedule('spindle', p)} />
      {message && <div role="alert" className="diag-error">{message}</div>}
    </div>
  )
}
