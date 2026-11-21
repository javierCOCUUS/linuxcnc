import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'

vi.mock('../../src/renderer/src/context/MachineDataContext', () => ({
  useMachineData: vi.fn(),
}))
vi.mock('../../src/renderer/src/context/RoleContext', () => ({
  useRole: vi.fn(),
}))

import { JogControlPanel } from '../../src/renderer/src/components/panels/JogControlPanel'
import { SpindlePanel } from '../../src/renderer/src/components/panels/SpindlePanel'
import { MacrosPanel } from '../../src/renderer/src/components/panels/MacrosPanel'
import { useMachineData } from '../../src/renderer/src/context/MachineDataContext'
import { useRole } from '../../src/renderer/src/context/RoleContext'

const mockUseMachineData = vi.mocked(useMachineData)
const mockUseRole = vi.mocked(useRole)

function setStatus(state: string): void {
  mockUseMachineData.mockReturnValue({ data: { state } as never, error: null, stale: false, loading: false })
}
const disabled = (name: string | RegExp): boolean => (screen.getByRole('button', { name }) as HTMLButtonElement).disabled

beforeEach(() => {
  vi.clearAllMocks()
  window.localStorage.setItem('mcp-cnc.macros', JSON.stringify([{ id: 'a', name: 'Aparcar', gcode: 'G0 Z5', confirm: false }]))
  window.electronAPI = {} as unknown as typeof window.electronAPI
})

describe('what an operator cannot do', () => {
  it('Jog Control: no jog, home or power, but the E-STOP stays available', () => {
    mockUseRole.mockReturnValue('operator')
    setStatus('IDLE')
    render(<JogControlPanel />)
    for (const name of ['Jog X+', 'Jog X-', 'Jog Z+', 'Home', 'Machine OFF']) expect(disabled(name)).toBe(true)
    expect(disabled('E-STOP')).toBe(false)
  })

  it('Jog Control: an operator cannot re-arm from E-stop or power on', () => {
    mockUseRole.mockReturnValue('operator')
    setStatus('ESTOP')
    const estop = render(<JogControlPanel />)
    expect(disabled('Rearmar E-stop')).toBe(true)
    estop.unmount()
    setStatus('OFF')
    render(<JogControlPanel />)
    expect(disabled('Machine ON')).toBe(true)
  })

  it('Jog Control: the machine role keeps working', () => {
    mockUseRole.mockReturnValue('machine')
    setStatus('IDLE')
    render(<JogControlPanel />)
    expect(disabled('Jog X+')).toBe(false)
  })

  it('Spindle: an operator cannot start, reverse or stop it', () => {
    mockUseRole.mockReturnValue('operator')
    setStatus('IDLE')
    render(<SpindlePanel />)
    for (const name of [/ON \(M3\)/, /REV \(M4\)/, /OFF \(M5\)/]) expect(disabled(name)).toBe(true)
  })

  it('Spindle: the machine role keeps working', () => {
    mockUseRole.mockReturnValue('machine')
    setStatus('IDLE')
    render(<SpindlePanel />)
    expect(disabled(/ON \(M3\)/)).toBe(false)
  })

  it('Macros: an operator cannot run a macro', () => {
    mockUseRole.mockReturnValue('operator')
    setStatus('IDLE')
    render(<MacrosPanel />)
    expect(disabled('Aparcar')).toBe(true)
  })

  it('Macros: the machine role keeps working', () => {
    mockUseRole.mockReturnValue('machine')
    setStatus('IDLE')
    render(<MacrosPanel />)
    expect(disabled('Aparcar')).toBe(false)
  })
})
