import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { StatusBar } from '../../src/renderer/src/components/StatusBar'
import * as hook from '../../src/renderer/src/hooks/useMachineStatus'

vi.mock('../../src/renderer/src/hooks/useMachineStatus')

const idleStatus = {
  state: 'IDLE' as const,
  backend: 'linuxcncrsh' as const,
  position: { x: 10.5, y: 20.0, z: -5.123 },
  spindle: { speed: 0, state: 'off' },
  tool: 2, feed: 0, units: 'mm'
}

describe('StatusBar', () => {
  it('shows "Connecting..." when status is null', () => {
    vi.mocked(hook.useMachineStatus).mockReturnValue({ status: null, error: null })
    render(<StatusBar />)
    expect(screen.getByText('Connecting...')).toBeInTheDocument()
  })

  it('shows machine state and XYZ position when status available', () => {
    vi.mocked(hook.useMachineStatus).mockReturnValue({ status: idleStatus, error: null })
    render(<StatusBar />)
    expect(screen.getByText('IDLE')).toBeInTheDocument()
    expect(screen.getByText('X:10.500')).toBeInTheDocument()
    expect(screen.getByText('Y:20.000')).toBeInTheDocument()
    expect(screen.getByText('Z:-5.123')).toBeInTheDocument()
  })

  it('shows tool number and units', () => {
    vi.mocked(hook.useMachineStatus).mockReturnValue({ status: idleStatus, error: null })
    render(<StatusBar />)
    expect(screen.getByText('T:2')).toBeInTheDocument()
    expect(screen.getByText('mm')).toBeInTheDocument()
  })

  it('shows error text when error is present', () => {
    vi.mocked(hook.useMachineStatus).mockReturnValue({ status: null, error: 'Connection refused' })
    render(<StatusBar />)
    expect(screen.getByText(/Connection refused/)).toBeInTheDocument()
  })
})
