import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { DiagnosticPanel } from '../../src/renderer/src/components/panels/DiagnosticPanel'
import * as ctx from '../../src/renderer/src/context/MachineDataContext'
import type { MachineDataContextValue } from '../../src/renderer/src/context/MachineDataContext'

vi.mock('../../src/renderer/src/context/MachineDataContext', async (importOriginal) => {
  const original = await importOriginal<typeof ctx>()
  return { ...original, useMachineData: vi.fn() }
})

function makeCtx(overrides: Partial<MachineDataContextValue> = {}): MachineDataContextValue {
  return { data: null, error: null, stale: false, loading: false, ...overrides }
}

const fullSystem = {
  backend: 'linuxcncrsh' as const,
  target: 'miniPC',
  mode: 'manual',
  machine: 'on',
  estop: 'off',
  program_status: 'IDLE',
  raw: ['axis 0 pos 1.0', 'axis 1 pos 2.0'],
}

const fullStatus = {
  state: 'IDLE' as const,
  position: { x: 0, y: 0, z: 0 },
  homed: [],
  spindle: { on: false, speed: 0, direction: 'off' },
  feed_rate: 0,
  active_gcode: '',
  system: fullSystem,
}

beforeEach(() => {
  vi.mocked(ctx.useMachineData).mockReturnValue(makeCtx())
})

describe('DiagnosticPanel', () => {
  it('renders without crashing when data is null', () => {
    vi.mocked(ctx.useMachineData).mockReturnValue(makeCtx({ data: null, loading: false }))
    expect(() => render(<DiagnosticPanel />)).not.toThrow()
  })

  it('shows — placeholders while loading', () => {
    vi.mocked(ctx.useMachineData).mockReturnValue(makeCtx({ loading: true }))
    render(<DiagnosticPanel />)
    expect(screen.getAllByText('—').length).toBeGreaterThan(0)
  })

  it('shows error banner when error is set and data is null', () => {
    vi.mocked(ctx.useMachineData).mockReturnValue(makeCtx({ error: 'HTTP 503', data: null }))
    render(<DiagnosticPanel />)
    expect(screen.getByRole('alert')).toHaveTextContent('HTTP 503')
  })

  it('shows estop badge', () => {
    vi.mocked(ctx.useMachineData).mockReturnValue(makeCtx({ data: fullStatus }))
    render(<DiagnosticPanel />)
    expect(screen.getByText('off')).toBeInTheDocument()
  })

  it('shows machine badge', () => {
    vi.mocked(ctx.useMachineData).mockReturnValue(makeCtx({ data: fullStatus }))
    render(<DiagnosticPanel />)
    expect(screen.getByText('on')).toBeInTheDocument()
  })

  it('shows mode', () => {
    vi.mocked(ctx.useMachineData).mockReturnValue(makeCtx({ data: fullStatus }))
    render(<DiagnosticPanel />)
    expect(screen.getByText('manual')).toBeInTheDocument()
  })

  it('shows program_status', () => {
    vi.mocked(ctx.useMachineData).mockReturnValue(makeCtx({ data: fullStatus }))
    render(<DiagnosticPanel />)
    expect(screen.getByText('IDLE')).toBeInTheDocument()
  })

  it('shows backend', () => {
    vi.mocked(ctx.useMachineData).mockReturnValue(makeCtx({ data: fullStatus }))
    render(<DiagnosticPanel />)
    expect(screen.getByText('linuxcncrsh')).toBeInTheDocument()
  })

  it('shows target', () => {
    vi.mocked(ctx.useMachineData).mockReturnValue(makeCtx({ data: fullStatus }))
    render(<DiagnosticPanel />)
    expect(screen.getByText('miniPC')).toBeInTheDocument()
  })

  it('shows raw lines', () => {
    vi.mocked(ctx.useMachineData).mockReturnValue(makeCtx({ data: fullStatus }))
    render(<DiagnosticPanel />)
    expect(screen.getByText('axis 0 pos 1.0')).toBeInTheDocument()
    expect(screen.getByText('axis 1 pos 2.0')).toBeInTheDocument()
  })

  it('handles missing system fields gracefully', () => {
    vi.mocked(ctx.useMachineData).mockReturnValue(
      makeCtx({ data: { ...fullStatus, system: { backend: 'stub' } } })
    )
    expect(() => render(<DiagnosticPanel />)).not.toThrow()
  })
})
