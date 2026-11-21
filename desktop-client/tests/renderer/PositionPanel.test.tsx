import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'

vi.mock('../../src/renderer/src/context/MachineDataContext', () => ({
  useMachineData: vi.fn(),
}))
vi.mock('../../src/renderer/src/context/RoleContext', () => ({
  useRole: vi.fn(),
}))
vi.mock('../../src/renderer/src/components/panels/PositionXYZPanel', () => ({
  PositionXYZPanel: () => <div data-testid="xyz" />,
}))

import { PositionPanel } from '../../src/renderer/src/components/panels/PositionPanel'
import { useMachineData } from '../../src/renderer/src/context/MachineDataContext'
import { useRole } from '../../src/renderer/src/context/RoleContext'

const mockUseMachineData = vi.mocked(useMachineData)
const mockUseRole = vi.mocked(useRole)
const positionCommand = vi.fn()
const homeAll = vi.fn()

function setStatus(state: string, stale = false): void {
  mockUseMachineData.mockReturnValue({ data: { state } as never, error: null, stale, loading: false })
}
const button = (name: string): HTMLButtonElement => screen.getByRole('button', { name }) as HTMLButtonElement
const NAMES = ['X = 0', 'Y = 0', 'Z = 0', 'GO TO ZERO', 'IR A PARK', 'REF ALL HOME']

beforeEach(() => {
  vi.clearAllMocks()
  positionCommand.mockResolvedValue({})
  homeAll.mockResolvedValue({})
  window.electronAPI = { positionCommand, homeAll } as unknown as typeof window.electronAPI
  mockUseRole.mockReturnValue('machine')
  setStatus('IDLE')
})

describe('PositionPanel', () => {
  it('shows the position readout', () => {
    render(<PositionPanel />)
    expect(screen.getByTestId('xyz')).toBeTruthy()
  })

  it('zeroes the chosen axis', async () => {
    render(<PositionPanel />)
    fireEvent.click(button('Y = 0'))
    await waitFor(() => expect(positionCommand).toHaveBeenCalledWith({ action: 'zero', axis: 'Y' }))
  })

  it('goes to zero and to the park position', async () => {
    render(<PositionPanel />)
    fireEvent.click(button('GO TO ZERO'))
    await waitFor(() => expect(positionCommand).toHaveBeenCalledWith({ action: 'goto-zero' }))
    fireEvent.click(button('IR A PARK'))
    await waitFor(() => expect(positionCommand).toHaveBeenCalledWith({ action: 'park' }))
  })

  it('homes every axis', async () => {
    render(<PositionPanel />)
    fireEvent.click(button('REF ALL HOME'))
    await waitFor(() => expect(homeAll).toHaveBeenCalledTimes(1))
  })

  it.each(['ESTOP', 'OFF', 'RUNNING', 'PAUSED', 'MDI', 'UNAVAILABLE'])('disables every action in %s', state => {
    setStatus(state)
    render(<PositionPanel />)
    for (const name of NAMES) expect(button(name).disabled).toBe(true)
  })

  it('disables every action for an operator and with a stale status', () => {
    mockUseRole.mockReturnValue('operator')
    const first = render(<PositionPanel />)
    for (const name of NAMES) expect(button(name).disabled).toBe(true)
    first.unmount()
    mockUseRole.mockReturnValue('machine')
    setStatus('IDLE', true)
    render(<PositionPanel />)
    for (const name of NAMES) expect(button(name).disabled).toBe(true)
  })

  it('shows why a move was refused, such as the missing safe coordinates', async () => {
    positionCommand.mockRejectedValue(new Error("Error invoking remote method 'machine:position': Error: Z_SAFE_G53 is not configured"))
    render(<PositionPanel />)
    fireEvent.click(button('GO TO ZERO'))
    expect((await screen.findByRole('alert')).textContent).toBe('Z_SAFE_G53 is not configured')
  })
})
