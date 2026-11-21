import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'

vi.mock('../../src/renderer/src/context/MachineDataContext', () => ({
  useMachineData: vi.fn(),
}))

import { JogControlPanel } from '../../src/renderer/src/components/panels/JogControlPanel'
import { useMachineData } from '../../src/renderer/src/context/MachineDataContext'

const mockUseMachineData = vi.mocked(useMachineData)

function setState(state: string, extra: { stale?: boolean } = {}): void {
  mockUseMachineData.mockReturnValue({
    data: { state } as never,
    error: null,
    stale: extra.stale ?? false,
    loading: false,
  })
}

const api = {
  jog: vi.fn(),
  setEstop: vi.fn(),
  setPower: vi.fn(),
  homeAll: vi.fn(),
}

beforeEach(() => {
  vi.clearAllMocks()
  Object.values(api).forEach(fn => fn.mockResolvedValue({ status: 'ok' }))
  window.electronAPI = { ...api } as unknown as typeof window.electronAPI
  setState('IDLE')
})

describe('JogControlPanel enabling rules', () => {
  it('enables jog, home and power off only when the machine is IDLE', () => {
    render(<JogControlPanel />)
    expect((screen.getByLabelText('Jog X+') as HTMLButtonElement).disabled).toBe(false)
    expect((screen.getByText('Home') as HTMLButtonElement).disabled).toBe(false)
    expect((screen.getByText('Machine OFF') as HTMLButtonElement).disabled).toBe(false)
    expect((screen.getByText('Rearmar E-stop') as HTMLButtonElement).disabled).toBe(true)
    expect((screen.getByText('Machine ON') as HTMLButtonElement).disabled).toBe(true)
  })

  it('in ESTOP only allows re-arming', () => {
    setState('ESTOP')
    render(<JogControlPanel />)
    expect((screen.getByText('Rearmar E-stop') as HTMLButtonElement).disabled).toBe(false)
    expect((screen.getByLabelText('Jog X+') as HTMLButtonElement).disabled).toBe(true)
    expect((screen.getByText('Home') as HTMLButtonElement).disabled).toBe(true)
    expect((screen.getByText('Machine ON') as HTMLButtonElement).disabled).toBe(true)
  })

  it('when powered off only allows Machine ON', () => {
    setState('OFF')
    render(<JogControlPanel />)
    expect((screen.getByText('Machine ON') as HTMLButtonElement).disabled).toBe(false)
    expect((screen.getByLabelText('Jog X+') as HTMLButtonElement).disabled).toBe(true)
  })

  it.each(['RUNNING', 'PAUSED', 'MDI', 'UNAVAILABLE'])('does not allow jogging in %s', state => {
    setState(state)
    render(<JogControlPanel />)
    expect((screen.getByLabelText('Jog X+') as HTMLButtonElement).disabled).toBe(true)
  })

  it('does not allow motion while the status is stale', () => {
    setState('IDLE', { stale: true })
    render(<JogControlPanel />)
    expect((screen.getByLabelText('Jog X+') as HTMLButtonElement).disabled).toBe(true)
    expect(screen.getByText('estado desactualizado')).toBeTruthy()
  })

  it('keeps E-STOP enabled in every state', () => {
    for (const state of ['IDLE', 'ESTOP', 'OFF', 'RUNNING', 'UNAVAILABLE']) {
      setState(state)
      const { unmount } = render(<JogControlPanel />)
      expect((screen.getByText('E-STOP') as HTMLButtonElement).disabled).toBe(false)
      unmount()
    }
  })

  it('disables jogging when the speed is invalid', () => {
    render(<JogControlPanel />)
    const input = screen.getByLabelText('Velocidad (mm/min)')
    for (const bad of ['0', '-5', '', '99999']) {
      fireEvent.change(input, { target: { value: bad } })
      expect((screen.getByLabelText('Jog X+') as HTMLButtonElement).disabled).toBe(true)
    }
    fireEvent.change(input, { target: { value: '300' } })
    expect((screen.getByLabelText('Jog X+') as HTMLButtonElement).disabled).toBe(false)
  })
})

describe('JogControlPanel axes', () => {
  it('shows X, Y, Z and hides A, B, C until the extra axes are enabled', () => {
    render(<JogControlPanel />)
    expect(screen.getByLabelText('Jog Z+')).toBeTruthy()
    expect(screen.queryByLabelText('Jog A+')).toBeNull()
    fireEvent.click(screen.getByLabelText('Ejes extra (A, B, C)'))
    expect(screen.getByLabelText('Jog A+')).toBeTruthy()
    expect(screen.getByLabelText('Jog B-')).toBeTruthy()
    expect(screen.getByLabelText('Jog C+')).toBeTruthy()
  })
})

describe('JogControlPanel actions', () => {
  it('jogs the chosen axis by the chosen step and speed', async () => {
    render(<JogControlPanel />)
    fireEvent.click(screen.getByText('10'))
    fireEvent.change(screen.getByLabelText('Velocidad (mm/min)'), { target: { value: '300' } })
    fireEvent.click(screen.getByLabelText('Jog Y-'))
    await waitFor(() => expect(api.jog).toHaveBeenCalledWith({ axis: 'Y', distance: -10, speed: 300 }))
  })

  it('uses a step of 1 mm and 600 mm/min by default', async () => {
    render(<JogControlPanel />)
    fireEvent.click(screen.getByLabelText('Jog X+'))
    await waitFor(() => expect(api.jog).toHaveBeenCalledWith({ axis: 'X', distance: 1, speed: 600 }))
  })

  it('jogs an extra axis once enabled', async () => {
    render(<JogControlPanel />)
    fireEvent.click(screen.getByLabelText('Ejes extra (A, B, C)'))
    fireEvent.click(screen.getByLabelText('Jog A+'))
    await waitFor(() => expect(api.jog).toHaveBeenCalledWith({ axis: 'A', distance: 1, speed: 600 }))
  })

  it('E-STOP sends active=true', async () => {
    render(<JogControlPanel />)
    fireEvent.click(screen.getByText('E-STOP'))
    await waitFor(() => expect(api.setEstop).toHaveBeenCalledWith(true))
  })

  it('Rearmar sends active=false', async () => {
    setState('ESTOP')
    render(<JogControlPanel />)
    fireEvent.click(screen.getByText('Rearmar E-stop'))
    await waitFor(() => expect(api.setEstop).toHaveBeenCalledWith(false))
  })

  it('Machine ON, Machine OFF and Home call their commands', async () => {
    setState('OFF')
    const first = render(<JogControlPanel />)
    fireEvent.click(screen.getByText('Machine ON'))
    await waitFor(() => expect(api.setPower).toHaveBeenCalledWith(true))
    first.unmount()

    setState('IDLE')
    render(<JogControlPanel />)
    fireEvent.click(screen.getByText('Machine OFF'))
    await waitFor(() => expect(api.setPower).toHaveBeenCalledWith(false))
    fireEvent.click(screen.getByText('Home'))
    await waitFor(() => expect(api.homeAll).toHaveBeenCalledTimes(1))
  })

  it('shows the backend reason when a command is refused, without the Electron prefix', async () => {
    api.jog.mockRejectedValue(new Error("Error invoking remote method 'machine:jog': Error: LinuxCNC is in E-stop"))
    render(<JogControlPanel />)
    fireEvent.click(screen.getByLabelText('Jog X+'))
    const alert = await screen.findByRole('alert')
    expect(alert.textContent).toBe('LinuxCNC is in E-stop')
  })

  it('blocks further jogs while a command is in flight, but never blocks E-STOP', async () => {
    let release: (v: unknown) => void = () => {}
    api.jog.mockReturnValue(new Promise(resolve => { release = resolve }))
    render(<JogControlPanel />)
    fireEvent.click(screen.getByLabelText('Jog X+'))
    await waitFor(() => expect((screen.getByLabelText('Jog X+') as HTMLButtonElement).disabled).toBe(true))
    expect((screen.getByText('E-STOP') as HTMLButtonElement).disabled).toBe(false)
    fireEvent.click(screen.getByText('E-STOP'))
    await waitFor(() => expect(api.setEstop).toHaveBeenCalledWith(true))
    release({ status: 'moving' })
    await waitFor(() => expect((screen.getByLabelText('Jog X+') as HTMLButtonElement).disabled).toBe(false))
  })
})
