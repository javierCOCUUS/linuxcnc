import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'

vi.mock('../../src/renderer/src/context/MachineDataContext', () => ({
  useMachineData: vi.fn(),
}))

import { GlobalStatus } from '../../src/renderer/src/components/GlobalStatus'
import { useMachineData } from '../../src/renderer/src/context/MachineDataContext'

const mockUseMachineData = vi.mocked(useMachineData)
const setEstop = vi.fn()

function setState(state: string | null, stale = false): void {
  mockUseMachineData.mockReturnValue({
    data: state ? ({ state } as never) : null,
    error: null,
    stale,
    loading: false,
  })
}

beforeEach(() => {
  vi.clearAllMocks()
  setEstop.mockResolvedValue({ status: 'estop_on' })
  window.electronAPI = { setEstop } as unknown as typeof window.electronAPI
  setState('IDLE')
})

describe('GlobalStatus', () => {
  it('shows the machine state', () => {
    setState('ESTOP')
    render(<GlobalStatus />)
    expect(screen.getByLabelText('Machine state').textContent).toBe('ESTOP')
  })

  it('shows UNAVAILABLE when there is no data yet', () => {
    setState(null)
    render(<GlobalStatus />)
    expect(screen.getByLabelText('Machine state').textContent).toBe('UNAVAILABLE')
  })

  it('warns when the status is stale', () => {
    setState('IDLE', true)
    render(<GlobalStatus />)
    expect(screen.getByText('sin datos recientes')).toBeTruthy()
  })

  it('sends the emergency stop in every state, even with no data', async () => {
    for (const state of ['IDLE', 'ESTOP', 'OFF', 'RUNNING', null]) {
      setEstop.mockClear()
      setState(state)
      const { unmount } = render(<GlobalStatus />)
      const button = screen.getByLabelText('Emergency stop') as HTMLButtonElement
      expect(button.disabled).toBe(false)
      fireEvent.click(button)
      await waitFor(() => expect(setEstop).toHaveBeenCalledWith(true))
      unmount()
    }
  })

  it('shows why the stop failed, without the Electron prefix', async () => {
    setEstop.mockRejectedValue(new Error("Error invoking remote method 'machine:estop': Error: HTTP 502"))
    render(<GlobalStatus />)
    fireEvent.click(screen.getByLabelText('Emergency stop'))
    expect((await screen.findByRole('alert')).textContent).toBe('HTTP 502')
  })

  it('clears an earlier error after a successful stop', async () => {
    setEstop.mockRejectedValueOnce(new Error('HTTP 502'))
    render(<GlobalStatus />)
    fireEvent.click(screen.getByLabelText('Emergency stop'))
    await screen.findByRole('alert')
    fireEvent.click(screen.getByLabelText('Emergency stop'))
    await waitFor(() => expect(screen.queryByRole('alert')).toBeNull())
  })
})
