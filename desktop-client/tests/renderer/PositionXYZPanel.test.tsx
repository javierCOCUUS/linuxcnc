import { render, screen } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach } from 'vitest'
import { PositionXYZPanel } from '../../src/renderer/src/components/panels/PositionXYZPanel'
import * as hook from '../../src/renderer/src/hooks/usePositionXYZ'

vi.mock('../../src/renderer/src/hooks/usePositionXYZ')

type HookResult = hook.UsePositionXYZResult

function makeResult(overrides: Partial<HookResult> = {}): HookResult {
  return {
    position: null,
    homed: [],
    error: null,
    stale: false,
    loading: false,
    ...overrides,
  }
}

const basePosition = { x: 10.5, y: -3.25, z: 0.0 }

describe('PositionXYZPanel', () => {
  beforeEach(() => {
    vi.mocked(hook.usePositionXYZ).mockReturnValue(makeResult())
  })

  it('shows dash placeholders while loading', () => {
    vi.mocked(hook.usePositionXYZ).mockReturnValue(makeResult({ loading: true }))
    render(<PositionXYZPanel />)
    expect(screen.getAllByText('—')).toHaveLength(3)
  })

  it('shows error when no position and error set', () => {
    vi.mocked(hook.usePositionXYZ).mockReturnValue(
      makeResult({ error: 'Connection refused' })
    )
    render(<PositionXYZPanel />)
    expect(screen.getByRole('alert')).toHaveTextContent('Connection refused')
  })

  it('renders X Y Z values formatted to 3 decimal places', () => {
    vi.mocked(hook.usePositionXYZ).mockReturnValue(
      makeResult({ position: basePosition })
    )
    render(<PositionXYZPanel />)
    expect(screen.getByText('10.500')).toBeInTheDocument()
    expect(screen.getByText('-3.250')).toBeInTheDocument()
    expect(screen.getByText('0.000')).toBeInTheDocument()
  })

  it('renders axis labels X Y Z', () => {
    vi.mocked(hook.usePositionXYZ).mockReturnValue(
      makeResult({ position: basePosition })
    )
    render(<PositionXYZPanel />)
    expect(screen.getByText('X')).toBeInTheDocument()
    expect(screen.getByText('Y')).toBeInTheDocument()
    expect(screen.getByText('Z')).toBeInTheDocument()
  })

  it('homed dot is green for homed axes', () => {
    vi.mocked(hook.usePositionXYZ).mockReturnValue(
      makeResult({ position: basePosition, homed: ['X', 'Z'] })
    )
    render(<PositionXYZPanel />)
    const dots = document.querySelectorAll('.pos-homed-dot')
    expect((dots[0] as HTMLElement).style.background).toBe('rgb(34, 197, 94)')
    expect((dots[1] as HTMLElement).style.background).toBe('rgb(68, 68, 68)')
    expect((dots[2] as HTMLElement).style.background).toBe('rgb(34, 197, 94)')
  })

  it('homed dot is grey when no axes homed', () => {
    vi.mocked(hook.usePositionXYZ).mockReturnValue(
      makeResult({ position: basePosition, homed: [] })
    )
    render(<PositionXYZPanel />)
    const dots = document.querySelectorAll('.pos-homed-dot')
    dots.forEach(dot => {
      expect((dot as HTMLElement).style.background).toBe('rgb(68, 68, 68)')
    })
  })

  it('reduces value opacity and shows stale label when stale', () => {
    vi.mocked(hook.usePositionXYZ).mockReturnValue(
      makeResult({ position: basePosition, stale: true })
    )
    render(<PositionXYZPanel />)
    expect(screen.getByText('stale')).toBeInTheDocument()
    const values = document.querySelectorAll('.pos-value')
    values.forEach(v => {
      expect((v as HTMLElement).style.opacity).toBe('0.5')
    })
  })

  it('does not show stale label when not stale', () => {
    vi.mocked(hook.usePositionXYZ).mockReturnValue(
      makeResult({ position: basePosition })
    )
    render(<PositionXYZPanel />)
    expect(screen.queryByText('stale')).not.toBeInTheDocument()
  })

  it('renders without crashing when position fields are missing', () => {
    vi.mocked(hook.usePositionXYZ).mockReturnValue(
      makeResult({ position: null, loading: false })
    )
    expect(() => render(<PositionXYZPanel />)).not.toThrow()
  })
})
