import type { HalPin } from '../types/api'

export interface HalInput {
  /** Input number as the 7i95 labels it, e.g. "08". */
  id: string
  /** Full HAL pin name of the physical input, e.g. hm2_7i95.0.inmux.00.input-08. */
  pin: string
  /** Physical state of the input (TRUE = current flowing / LED on). */
  on: boolean
  /** HAL signal the input (or its -not variant) is wired to, if any. */
  signal: string | null
  /** True when the signal is fed by the inverted (-not) pin. */
  inverted: boolean
  /** Current value of the wired signal, null when no signal is wired. */
  signalOn: boolean | null
}

const INPUT_RE = /\.input-(\d+)(-not)?$/
const SIGNAL_RE = /==>\s*(\S+)/

/**
 * Turns the pin list returned by GET /hal/pins?filter=inmux.00.input- into one
 * entry per physical input. Pins such as input-NN-slow or raw-input-NN are ignored.
 * The signal name is taken from either input-NN or input-NN-not, whichever is wired.
 */
export function parseHalInputs(pins: HalPin[]): HalInput[] {
  const byId = new Map<string, HalInput>()

  for (const pin of pins) {
    const m = INPUT_RE.exec(pin.name)
    if (!m) continue
    const [, id, notSuffix] = m
    const isNot = Boolean(notSuffix)

    let entry = byId.get(id)
    if (!entry) {
      entry = { id, pin: '', on: false, signal: null, inverted: false, signalOn: null }
      byId.set(id, entry)
    }

    if (!isNot) {
      entry.pin = pin.name
      entry.on = pin.value === 'TRUE'
    }

    if (entry.signal === null) {
      const sig = SIGNAL_RE.exec(pin.raw ?? '')
      if (sig) {
        entry.signal = sig[1]
        entry.inverted = isNot
        entry.signalOn = pin.value === 'TRUE'
      }
    }
  }

  return [...byId.values()]
    .filter(input => input.pin !== '')
    .sort((a, b) => Number(a.id) - Number(b.id))
}
