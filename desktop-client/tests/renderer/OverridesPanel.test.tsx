import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, act } from '@testing-library/react'

vi.mock('../../src/renderer/src/context/MachineDataContext', () => ({
  useMachineData: vi.fn(),
}))

import { OverridesPanel } from '../../src/renderer/src/components/panels/OverridesPanel'
import { useMachineData } from '../../src/renderer/src/context/MachineDataContext'

const mockUseMachineData = vi.mocked(useMachineData)
const setOverride = vi.fn()

function setStatus(state: string, feed = 100, stale = false): void {
  mockUseMachineData.mockReturnValue({ data: { state, feed_rate: feed } as never, error: null, stale, loading: false })
}
const change = (label: string, value: number): void => {
  fireEvent.change(screen.getByLabelText(label), { target: { value: String(value) } })
}
const flush = async (ms = 400): Promise<void> => { await act(async () => { vi.advanceTimersByTime(ms) }) }

beforeEach(() => {
  vi.useFakeTimers()
  vi.clearAllMocks()
  setOverride.mockResolvedValue({ status: 'ok' })
  window.electronAPI = { setOverride } as unknown as typeof window.electronAPI
  setStatus('IDLE', 100)
})
afterEach(() => { vi.useRealTimers() })

describe('OverridesPanel', () => {
  it('shows the feed override reported by the machine', () => {
    setStatus('IDLE', 80)
    render(<OverridesPanel />)
    expect(screen.getByTestId('ovr-feed-value').textContent).toBe('80%')
  })

  it('sends the feed override once the slider stops moving, not on every tick', async () => {
    render(<OverridesPanel />)
    change('Avance', 90); change('Avance', 95); change('Avance', 110)
    expect(setOverride).not.toHaveBeenCalled()
    await flush()
    expect(setOverride).toHaveBeenCalledTimes(1)
    expect(setOverride).toHaveBeenCalledWith({ kind: 'feed', percent: 110 })
  })

  it('shows the value being dragged straight away', () => {
    render(<OverridesPanel />)
    change('Avance', 60)
    expect(screen.getByTestId('ovr-feed-value').textContent).toBe('60%')
  })

  it('sends the spindle override separately from the feed', async () => {
    render(<OverridesPanel />)
    change('Spindle', 70)
    await flush()
    expect(setOverride).toHaveBeenCalledWith({ kind: 'spindle', percent: 70 })
    expect(setOverride).toHaveBeenCalledTimes(1)
  })

  it('presets send their value', async () => {
    render(<OverridesPanel />)
    fireEvent.click(screen.getByRole('button', { name: 'Avance 50%' }))
    await flush()
    expect(setOverride).toHaveBeenCalledWith({ kind: 'feed', percent: 50 })
  })

  it('goes back to the reported value after the command is sent', async () => {
    render(<OverridesPanel />)
    change('Avance', 60)
    await flush()
    expect(screen.getByTestId('ovr-feed-value').textContent).toBe('100%')
  })

  it('is disabled when the status is unavailable or stale', () => {
    setStatus('UNAVAILABLE')
    const first = render(<OverridesPanel />)
    expect((screen.getByLabelText('Avance') as HTMLInputElement).disabled).toBe(true)
    first.unmount()
    setStatus('IDLE', 100, true)
    render(<OverridesPanel />)
    expect((screen.getByLabelText('Avance') as HTMLInputElement).disabled).toBe(true)
  })

  it('works in any machine state, including E-stop and running', () => {
    for (const state of ['ESTOP', 'OFF', 'IDLE', 'RUNNING', 'PAUSED']) {
      setStatus(state)
      const { unmount } = render(<OverridesPanel />)
      expect((screen.getByLabelText('Avance') as HTMLInputElement).disabled).toBe(false)
      unmount()
    }
  })

  it('shows why a command was refused', async () => {
    setOverride.mockRejectedValue(new Error("Error invoking remote method 'machine:override': Error: HTTP 502"))
    render(<OverridesPanel />)
    change('Avance', 60)
    await flush()
    expect(screen.getByRole('alert').textContent).toBe('HTTP 502')
  })

  it('does not send after it is unmounted', async () => {
    const { unmount } = render(<OverridesPanel />)
    change('Avance', 60)
    unmount()
    await flush()
    expect(setOverride).not.toHaveBeenCalled()
  })
})
