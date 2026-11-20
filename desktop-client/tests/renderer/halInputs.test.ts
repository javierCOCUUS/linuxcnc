import { describe, it, expect } from 'vitest'
import { parseHalInputs } from '../../src/renderer/src/lib/halInputs'
import type { HalPin } from '../../src/renderer/src/types/api'

const P = 'hm2_7i95.0.inmux.00.'

function pin(name: string, value: 'TRUE' | 'FALSE', link = ''): HalPin {
  return {
    name: `${P}${name}`,
    value,
    raw: `    30  bit   OUT   ${value}  ${P}${name}${link}`,
  }
}

describe('parseHalInputs', () => {
  it('returns one entry per physical input, sorted by number', () => {
    const result = parseHalInputs([pin('input-10', 'FALSE'), pin('input-08', 'TRUE')])
    expect(result.map(r => r.id)).toEqual(['08', '10'])
    expect(result[0]).toMatchObject({ pin: `${P}input-08`, on: true })
    expect(result[1]).toMatchObject({ pin: `${P}input-10`, on: false })
  })

  it('takes the signal from the base pin when it is wired', () => {
    const [input] = parseHalInputs([
      pin('input-08', 'TRUE', ' ==> remote-estop0'),
      pin('input-08-not', 'FALSE'),
    ])
    expect(input).toMatchObject({ signal: 'remote-estop0', inverted: false, signalOn: true })
  })

  it('takes the signal from the -not pin and marks it inverted', () => {
    const [input] = parseHalInputs([
      pin('input-10', 'FALSE'),
      pin('input-10-not', 'TRUE', ' ==> neg-limit-joint-0'),
    ])
    expect(input).toMatchObject({
      on: false,
      signal: 'neg-limit-joint-0',
      inverted: true,
      signalOn: true,
    })
  })

  it('leaves signal null when nothing is wired', () => {
    const [input] = parseHalInputs([pin('input-03', 'FALSE'), pin('input-03-not', 'TRUE')])
    expect(input).toMatchObject({ signal: null, signalOn: null, inverted: false })
  })

  it('ignores slow, raw and unrelated pins', () => {
    const result = parseHalInputs([
      pin('input-08', 'FALSE'),
      pin('input-08-slow', 'FALSE'),
      pin('raw-input-08', 'FALSE'),
      pin('raw-input-08-not', 'TRUE'),
      pin('output-01', 'FALSE'),
    ])
    expect(result).toHaveLength(1)
    expect(result[0].id).toBe('08')
  })

  it('drops an input that only has the -not pin', () => {
    expect(parseHalInputs([pin('input-05-not', 'TRUE')])).toEqual([])
  })

  it('copes with pins that have no raw line', () => {
    const [input] = parseHalInputs([{ name: `${P}input-01`, value: 'TRUE' }])
    expect(input).toMatchObject({ id: '01', on: true, signal: null })
  })

  it('returns an empty list for no pins', () => {
    expect(parseHalInputs([])).toEqual([])
  })
})
