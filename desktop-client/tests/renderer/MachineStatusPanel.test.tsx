import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { MachineStatusPanel } from '../../src/renderer/src/components/panels/MachineStatusPanel'
import * as hook from '../../src/renderer/src/hooks/useMachineStatus'
import type { UseMachineStatusResult } from '../../src/renderer/src/hooks/useMachineStatus'

vi.mock('../../src/renderer/src/hooks/useMachineStatus')

function makeResult(overrides: Partial<UseMachineStatusResult> = {}): UseMachineStatusResult {
  return { data: null, error: null, stale: false, loading: false, ...overrides }
}

const idleStatus = {
  state: 'IDLE' as const,
  position: { x: 1, y: 2, z: 3 },
  homed: ['X', 'Y', 'Z'],
  spindle: { on: false, speed: 0, direction: 'off' },
  feed_rate: 100,
  active_gcode: 'G54 G17 G90',
  system: { backend: 'stub' as const },
}

beforeEach(() => {
  vi.mocked(hook.useMachineStatus).mockReturnValue(makeResult())
})

describe('MachineStatusPanel', () => {
  it('shows — placeholders while loading', () => {
    vi.mocked(hook.useMachineStatus).mockReturnValue(makeResult({ loading: true }))
    render(<MachineStatusPanel />)
    expect(screen.getAllByText('—').length).toBeGreaterThan(0)
  })

  it('renders IDLE state badge', () => {
    vi.mocked(hook.useMachineStatus).mockReturnValue(makeResult({ data: idleStatus }))
    render(<MachineStatusPanel />)
    expect(screen.getByText('IDLE')).toBeInTheDocument()
  })

  it('renders RUN state badge', () => {
    vi.mocked(hook.useMachineStatus).mockReturnValue(
      makeResult({ data: { ...idleStatus, state: 'RUN' } })
    )
    render(<MachineStatusPanel />)
    expect(screen.getByText('RUN')).toBeInTheDocument()
  })

  it('renders ESTOP state badge', () => {
    vi.mocked(hook.useMachineStatus).mockReturnValue(
      makeResult({ data: { ...idleStatus, state: 'ESTOP' } })
    )
    render(<MachineStatusPanel />)
    expect(screen.getByText('ESTOP')).toBeInTheDocument()
  })

  it('shows spindle OFF when spindle.on is false', () => {
    vi.mocked(hook.useMachineStatus).mockReturnValue(makeResult({ data: idleStatus }))
    render(<MachineStatusPanel />)
    expect(screen.getByText(/OFF/i)).toBeInTheDocument()
  })

  it('shows spindle ON with speed and direction', () => {
    vi.mocked(hook.useMachineStatus).mockReturnValue(
      makeResult({ data: { ...idleStatus, spindle: { on: true, speed: 12000, direction: 'CW' } } })
    )
    render(<MachineStatusPanel />)
    expect(screen.getByText(/12000/)).toBeInTheDocument()
    expect(screen.getByText(/CW/)).toBeInTheDocument()
  })

  it('shows feed rate', () => {
    vi.mocked(hook.useMachineStatus).mockReturnValue(makeResult({ data: idleStatus }))
    render(<MachineStatusPanel />)
    expect(screen.getByText(/100/)).toBeInTheDocument()
  })

  it('shows homed axes as space-separated string', () => {
    vi.mocked(hook.useMachineStatus).mockReturnValue(makeResult({ data: idleStatus }))
    render(<MachineStatusPanel />)
    expect(screen.getByText('X Y Z')).toBeInTheDocument()
  })

  it('shows None when homed array is empty', () => {
    vi.mocked(hook.useMachineStatus).mockReturnValue(
      makeResult({ data: { ...idleStatus, homed: [] } })
    )
    render(<MachineStatusPanel />)
    expect(screen.getByText(/none/i)).toBeInTheDocument()
  })

  it('shows active G-code', () => {
    vi.mocked(hook.useMachineStatus).mockReturnValue(makeResult({ data: idleStatus }))
    render(<MachineStatusPanel />)
    expect(screen.getByText('G54 G17 G90')).toBeInTheDocument()
  })

  it('shows error banner when system.error is set', () => {
    vi.mocked(hook.useMachineStatus).mockReturnValue(
      makeResult({
        data: {
          ...idleStatus,
          state: 'UNAVAILABLE',
          system: { backend: 'linuxcncrsh', error: 'Connection refused' },
        },
      })
    )
    render(<MachineStatusPanel />)
    expect(screen.getByRole('alert')).toHaveTextContent('Connection refused')
  })

  it('does not show error banner when system.error is absent', () => {
    vi.mocked(hook.useMachineStatus).mockReturnValue(makeResult({ data: idleStatus }))
    render(<MachineStatusPanel />)
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('appends (stale) to state text when stale is true', () => {
    vi.mocked(hook.useMachineStatus).mockReturnValue(
      makeResult({ data: idleStatus, stale: true })
    )
    render(<MachineStatusPanel />)
    expect(screen.getByText(/stale/i)).toBeInTheDocument()
  })

  it('shows fetch error message when data is null and error is set', () => {
    vi.mocked(hook.useMachineStatus).mockReturnValue(makeResult({ error: 'HTTP 503' }))
    render(<MachineStatusPanel />)
    expect(screen.getByText(/HTTP 503/)).toBeInTheDocument()
  })

  it('does not crash when backend returns partial data — Gotcha 3', () => {
    vi.mocked(hook.useMachineStatus).mockReturnValue(
      makeResult({
        data: {
          state: 'UNAVAILABLE',
          position: { x: 0, y: 0, z: 0 },
          homed: [],
          spindle: undefined as unknown as { on: boolean; speed: number; direction: string },
          feed_rate: undefined as unknown as number,
          active_gcode: undefined as unknown as string,
          system: { backend: 'linuxcncrsh' },
        },
      })
    )
    expect(() => render(<MachineStatusPanel />)).not.toThrow()
  })
})
