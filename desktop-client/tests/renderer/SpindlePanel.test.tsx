import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'

vi.mock('../../src/renderer/src/context/MachineDataContext', () => ({
  useMachineData: vi.fn(),
}))

import { SpindlePanel } from '../../src/renderer/src/components/panels/SpindlePanel'
import { useMachineData } from '../../src/renderer/src/context/MachineDataContext'

const mockUseMachineData = vi.mocked(useMachineData)
const setSpindle = vi.fn()

function setState(state: string, stale = false): void {
  mockUseMachineData.mockReturnValue({ data: { state } as never, error: null, stale, loading: false })
}
const disabled = (name: string | RegExp): boolean =>
  (screen.getByRole('button', { name }) as HTMLButtonElement).disabled

beforeEach(() => {
  vi.clearAllMocks()
  setSpindle.mockResolvedValue({ status: 'spindle_updated' })
  window.electronAPI = { setSpindle } as unknown as typeof window.electronAPI
  setState('IDLE')
})

describe('SpindlePanel', () => {
  it.each(['IDLE', 'MDI'])('can be commanded in %s', state => {
    setState(state)
    render(<SpindlePanel />)
    expect(disabled(/ON \(M3\)/)).toBe(false)
    expect(disabled(/OFF \(M5\)/)).toBe(false)
  })

  it.each(['ESTOP', 'OFF', 'RUNNING', 'PAUSED', 'UNAVAILABLE'])('cannot be commanded in %s', state => {
    setState(state)
    render(<SpindlePanel />)
    expect(disabled(/ON \(M3\)/)).toBe(true)
    expect(disabled(/REV \(M4\)/)).toBe(true)
    expect(disabled(/OFF \(M5\)/)).toBe(true)
  })

  it('cannot be commanded while the status is stale', () => {
    setState('IDLE', true)
    render(<SpindlePanel />)
    expect(disabled(/ON \(M3\)/)).toBe(true)
  })

  it('starts forward at the chosen rpm', async () => {
    render(<SpindlePanel />)
    fireEvent.click(screen.getByRole('button', { name: '18000' }))
    fireEvent.click(screen.getByRole('button', { name: /ON \(M3\)/ }))
    await waitFor(() => expect(setSpindle).toHaveBeenCalledWith({ state: 'on', rpm: 18000 }))
    expect(await screen.findByText('Ordenado: M3 S18000')).toBeTruthy()
  })

  it('starts in reverse', async () => {
    render(<SpindlePanel />)
    fireEvent.click(screen.getByRole('button', { name: /REV \(M4\)/ }))
    await waitFor(() => expect(setSpindle).toHaveBeenCalledWith({ state: 'reverse', rpm: 12000 }))
    expect(await screen.findByText('Ordenado: M4 S12000')).toBeTruthy()
  })

  it('stops with rpm 0', async () => {
    render(<SpindlePanel />)
    fireEvent.click(screen.getByRole('button', { name: /OFF \(M5\)/ }))
    await waitFor(() => expect(setSpindle).toHaveBeenCalledWith({ state: 'off', rpm: 0 }))
    expect(await screen.findByText('Ordenado: M5 (parado)')).toBeTruthy()
  })

  it('can stop even when the rpm field is invalid', async () => {
    render(<SpindlePanel />)
    fireEvent.change(screen.getByLabelText('rpm'), { target: { value: '' } })
    expect(disabled(/ON \(M3\)/)).toBe(true)
    expect(disabled(/OFF \(M5\)/)).toBe(false)
  })

  it.each(['0', '-100', '24001', '1.5', ''])('rejects the rpm "%s"', value => {
    render(<SpindlePanel />)
    fireEvent.change(screen.getByLabelText('rpm'), { target: { value } })
    expect(disabled(/ON \(M3\)/)).toBe(true)
    expect(disabled(/REV \(M4\)/)).toBe(true)
  })

  it('offers to apply a new rpm only while running and when it changed', async () => {
    render(<SpindlePanel />)
    expect(screen.queryByRole('button', { name: 'Aplicar rpm' })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: /ON \(M3\)/ }))
    await screen.findByText('Ordenado: M3 S12000')
    expect(disabled('Aplicar rpm')).toBe(true)
    fireEvent.click(screen.getByRole('button', { name: '6000' }))
    expect(disabled('Aplicar rpm')).toBe(false)
    fireEvent.click(screen.getByRole('button', { name: 'Aplicar rpm' }))
    await waitFor(() => expect(setSpindle).toHaveBeenLastCalledWith({ state: 'on', rpm: 6000 }))
  })

  it('shows why a command was refused, without the Electron prefix', async () => {
    setSpindle.mockRejectedValue(new Error("Error invoking remote method 'machine:spindle': Error: LinuxCNC is in E-stop"))
    render(<SpindlePanel />)
    fireEvent.click(screen.getByRole('button', { name: /ON \(M3\)/ }))
    expect((await screen.findByRole('alert')).textContent).toBe('LinuxCNC is in E-stop')
  })

  it('does not claim the spindle runs when the command failed', async () => {
    setSpindle.mockRejectedValue(new Error('HTTP 409'))
    render(<SpindlePanel />)
    fireEvent.click(screen.getByRole('button', { name: /ON \(M3\)/ }))
    await screen.findByRole('alert')
    expect(screen.queryByText(/Ordenado/)).toBeNull()
    expect(screen.getByText('SIN ORDEN')).toBeTruthy()
  })
})
