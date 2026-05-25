import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'

vi.mock('../../src/renderer/src/hooks/useMachineHealth', () => ({
  useMachineHealth: vi.fn(),
}))

import { ServicesPanel } from '../../src/renderer/src/components/panels/ServicesPanel'
import { useMachineHealth } from '../../src/renderer/src/hooks/useMachineHealth'

const mockUseMachineHealth = vi.mocked(useMachineHealth)

const baseHealth = {
  data: {
    backend: 'linuxcncrsh' as const,
    status: 'ok' as const,
    linuxcncrsh: { status: 'ok' as const, latency_ms: 10 },
    hal_bridge:  { status: 'ok' as const, latency_ms: 8 },
    mesa_pins:   { status: 'ok' as const, latency_ms: 20, count: 47 },
  },
  error: null,
  loading: false,
}

beforeEach(() => {
  vi.clearAllMocks()
  mockUseMachineHealth.mockReturnValue(baseHealth)
})

describe('ServicesPanel', () => {
  it('shows ok badge for linuxcncrsh when status ok', () => {
    render(<ServicesPanel />)
    expect(screen.getByText('linuxcncrsh')).toBeTruthy()
    const badge = screen.getAllByText('ok')
    expect(badge.length).toBeGreaterThanOrEqual(1)
  })

  it('shows ok badge for hal_bridge when status ok', () => {
    render(<ServicesPanel />)
    expect(screen.getByText('hal_bridge')).toBeTruthy()
  })

  it('shows ok badge for mesa_pins when status ok', () => {
    render(<ServicesPanel />)
    expect(screen.getByText('mesa_pins')).toBeTruthy()
  })

  it('shows down badge when service status is down', () => {
    mockUseMachineHealth.mockReturnValue({
      ...baseHealth,
      data: {
        ...baseHealth.data!,
        hal_bridge: { status: 'down' as const, latency_ms: 0, error: 'Connection refused' },
      },
    })
    render(<ServicesPanel />)
    expect(screen.getByText('down')).toBeTruthy()
  })

  it('shows error detail when service is down', () => {
    mockUseMachineHealth.mockReturnValue({
      ...baseHealth,
      data: {
        ...baseHealth.data!,
        hal_bridge: { status: 'down' as const, latency_ms: 0, error: 'Connection refused' },
      },
    })
    render(<ServicesPanel />)
    expect(screen.getByText(/Connection refused/i)).toBeTruthy()
  })

  it('shows loading state while data is null', () => {
    mockUseMachineHealth.mockReturnValue({ data: null, error: null, loading: true })
    render(<ServicesPanel />)
    expect(screen.getAllByText('—').length).toBeGreaterThan(0)
  })

  it('shows error message when hook has error and no data', () => {
    mockUseMachineHealth.mockReturnValue({ data: null, error: 'Network error', loading: false })
    render(<ServicesPanel />)
    expect(screen.getByRole('alert')).toBeTruthy()
    expect(screen.getByText(/Network error/i)).toBeTruthy()
  })

  it('shows mesa pin count when available', () => {
    render(<ServicesPanel />)
    expect(screen.getByText(/47/)).toBeTruthy()
  })

  it('does not call getMachineStatus directly', () => {
    const spy = vi.fn()
    window.electronAPI = { getMachineStatus: spy } as unknown as typeof window.electronAPI
    render(<ServicesPanel />)
    expect(spy).not.toHaveBeenCalled()
  })
})
