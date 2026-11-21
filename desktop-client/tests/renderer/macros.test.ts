import { describe, it, expect, beforeEach, vi } from 'vitest'
import { gcodeLines, loadMacros, newMacro, saveMacros } from '../../src/renderer/src/lib/macros'

beforeEach(() => {
  window.localStorage.clear()
  vi.restoreAllMocks()
})

describe('gcodeLines', () => {
  it('splits into trimmed lines and drops blank ones', () => {
    expect(gcodeLines('G0 X0 Y0\n\n  G0 Z5  \r\nM5')).toEqual(['G0 X0 Y0', 'G0 Z5', 'M5'])
  })

  it('drops comment-only lines but keeps lines that merely contain a comment', () => {
    expect(gcodeLines('; go home\n(park the head)\nG0 X0 (to zero)\nG0 Z5 ; up')).toEqual([
      'G0 X0 (to zero)', 'G0 Z5 ; up',
    ])
  })

  it('returns nothing for empty text', () => {
    expect(gcodeLines('')).toEqual([])
    expect(gcodeLines('  \n ; only a comment')).toEqual([])
  })
})

describe('macro storage', () => {
  it('starts empty', () => {
    expect(loadMacros()).toEqual([])
  })

  it('saves and loads macros', () => {
    const macros = [{ ...newMacro(), name: 'Park', gcode: 'G0 Z5', confirm: false }]
    saveMacros(macros)
    expect(loadMacros()).toEqual(macros)
  })

  it('creates macros with distinct ids that ask for confirmation by default', () => {
    const a = newMacro()
    const b = newMacro()
    expect(a.id).not.toBe(b.id)
    expect(a.confirm).toBe(true)
  })

  it('ignores stored data that is not valid JSON', () => {
    window.localStorage.setItem('mcp-cnc.macros', '{not json')
    expect(loadMacros()).toEqual([])
  })

  it('drops stored entries with the wrong shape and keeps the valid ones', () => {
    const good = { id: 'a', name: 'Park', gcode: 'G0 Z5', confirm: true }
    window.localStorage.setItem('mcp-cnc.macros', JSON.stringify([good, { id: 1 }, null, 'x', { ...good, confirm: 'yes' }]))
    expect(loadMacros()).toEqual([good])
  })

  it('ignores stored data that is not a list', () => {
    window.localStorage.setItem('mcp-cnc.macros', JSON.stringify({ a: 1 }))
    expect(loadMacros()).toEqual([])
  })

  it('does not throw when storage is unavailable', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('blocked') })
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('blocked') })
    expect(loadMacros()).toEqual([])
    expect(() => saveMacros([newMacro()])).not.toThrow()
  })
})
