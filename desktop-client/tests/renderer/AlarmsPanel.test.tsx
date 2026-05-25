import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { AlarmsPanel, deriveAlarms } from '../../src/renderer/src/components/panels/AlarmsPanel'
import * as ctx from '../../src/renderer/src/context/MachineDataContext'
import type { MachineDataContextValue } from '../../src/renderer/src/context/MachineDataContext'

vi.mock('../../src/renderer/src/context/MachineDataContext', async (importOriginal) => {
  const original = await importOriginal<typeof ctx>()
  return { ...original, useMachineData: vi.fn() }
})

function makeCtx(overrides: Partial<MachineDataContextValue> = {}): MachineDataContextValue {
  return { data: null, error: null, stale: false, loading: false, ...overrides }
}

const okSystem = {
  backend: 'stub' as const,
  estop: 'off',
  machine: 'on',
}

const okStatus = {
  state: 'IDLE' as const,
  position: { x: 0, y: 0, z: 0 },
  homed: [],
  spindle: { on: false, speed: 0, direction: 'off' },
  feed_rate: 0,
  active_gcode: '',
  system: okSystem,
}

beforeEach(() => {
  vi.mocked(ctx.useMachineData).mockReturnValue(makeCtx())
})

// ── deriveAlarms unit tests ────────────────────────────────────────────────

describe('deriveAlarms', () => {
  it('returns empty array when no conditions met', () => {
    const alarms = deriveAlarms({ data: okStatus, error: null, stale: false, loading: false })
    expect(alarms).toHaveLength(0)
  })

  it('returns ERROR alarm when estop is on', () => {
    const alarms = deriveAlarms({
      data: { ...okStatus, system: { ...okSystem, estop: 'on' } },
      error: null, stale: false, loading: false,
    })
    expect(alarms).toContainEqual(expect.objectContaining({ severity: 'error', message: 'E-stop activo' }))
  })

  it('returns WARN alarm when machine is off', () => {
    const alarms = deriveAlarms({
      data: { ...okStatus, system: { ...okSystem, machine: 'off' } },
      error: null, stale: false, loading: false,
    })
    expect(alarms).toContainEqual(expect.objectContaining({ severity: 'warn', message: 'Máquina apagada' }))
  })

  it('returns ERROR alarm when system.error is set', () => {
    const alarms = deriveAlarms({
      data: { ...okStatus, system: { ...okSystem, error: 'Connection refused' } },
      error: null, stale: false, loading: false,
    })
    expect(alarms).toContainEqual(expect.objectContaining({ severity: 'error', message: 'Connection refused' }))
  })

  it('returns WARN alarm when stale is true', () => {
    const alarms = deriveAlarms({
      data: okStatus, error: null, stale: true, loading: false,
    })
    expect(alarms).toContainEqual(expect.objectContaining({ severity: 'warn', message: 'Datos desactualizados' }))
  })

  it('can accumulate multiple alarms simultaneously', () => {
    const alarms = deriveAlarms({
      data: { ...okStatus, system: { ...okSystem, estop: 'on', machine: 'off' } },
      error: null, stale: true, loading: false,
    })
    expect(alarms.length).toBeGreaterThanOrEqual(3)
  })

  it('returns empty array when data is null', () => {
    const alarms = deriveAlarms({ data: null, error: null, stale: false, loading: false })
    expect(alarms).toHaveLength(0)
  })
})

// ── AlarmsPanel render tests ──────────────────────────────────────────────

describe('AlarmsPanel', () => {
  it('renders without crashing when data is null', () => {
    vi.mocked(ctx.useMachineData).mockReturnValue(makeCtx({ data: null }))
    expect(() => render(<AlarmsPanel />)).not.toThrow()
  })

  it('shows "Sistema OK" when no alarms', () => {
    vi.mocked(ctx.useMachineData).mockReturnValue(makeCtx({ data: okStatus }))
    render(<AlarmsPanel />)
    expect(screen.getByText(/sistema ok/i)).toBeInTheDocument()
  })

  it('shows E-stop alarm row when estop is on', () => {
    vi.mocked(ctx.useMachineData).mockReturnValue(
      makeCtx({ data: { ...okStatus, system: { ...okSystem, estop: 'on' } } })
    )
    render(<AlarmsPanel />)
    expect(screen.getByText('E-stop activo')).toBeInTheDocument()
  })

  it('shows Máquina apagada alarm when machine is off', () => {
    vi.mocked(ctx.useMachineData).mockReturnValue(
      makeCtx({ data: { ...okStatus, system: { ...okSystem, machine: 'off' } } })
    )
    render(<AlarmsPanel />)
    expect(screen.getByText('Máquina apagada')).toBeInTheDocument()
  })

  it('shows stale alarm when stale is true', () => {
    vi.mocked(ctx.useMachineData).mockReturnValue(makeCtx({ data: okStatus, stale: true }))
    render(<AlarmsPanel />)
    expect(screen.getByText('Datos desactualizados')).toBeInTheDocument()
  })
})
