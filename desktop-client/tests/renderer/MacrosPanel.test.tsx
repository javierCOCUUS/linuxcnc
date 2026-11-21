import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'

vi.mock('../../src/renderer/src/context/MachineDataContext', () => ({
  useMachineData: vi.fn(),
}))

import { MacrosPanel } from '../../src/renderer/src/components/panels/MacrosPanel'
import { useMachineData } from '../../src/renderer/src/context/MachineDataContext'

const mockUseMachineData = vi.mocked(useMachineData)
const sendGcode = vi.fn()

function setState(state: string, stale = false): void {
  mockUseMachineData.mockReturnValue({ data: { state } as never, error: null, stale, loading: false })
}

function seed(macros: object[]): void {
  window.localStorage.setItem('mcp-cnc.macros', JSON.stringify(macros))
}

const park = { id: 'p', name: 'Aparcar', gcode: 'G0 Z5\nG0 X0 Y0', confirm: false }

beforeEach(() => {
  vi.clearAllMocks()
  window.localStorage.clear()
  sendGcode.mockResolvedValue({ status: 'executed' })
  window.electronAPI = { sendGcode } as unknown as typeof window.electronAPI
  window.confirm = vi.fn(() => true)
  setState('IDLE')
})

describe('MacrosPanel', () => {
  it('explains how to add the first macro', () => {
    render(<MacrosPanel />)
    expect(screen.getByText(/No hay macros/)).toBeTruthy()
  })

  it('shows one button per saved macro', () => {
    seed([park, { ...park, id: 'q', name: 'Calibrar' }])
    render(<MacrosPanel />)
    expect(screen.getByRole('button', { name: 'Aparcar' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Calibrar' })).toBeTruthy()
  })

  it('runs a macro line by line, in order', async () => {
    seed([park])
    render(<MacrosPanel />)
    fireEvent.click(screen.getByRole('button', { name: 'Aparcar' }))
    await waitFor(() => expect(sendGcode).toHaveBeenCalledTimes(2))
    expect(sendGcode.mock.calls.map(c => c[0])).toEqual(['G0 Z5', 'G0 X0 Y0'])
    expect(await screen.findByText('«Aparcar» ejecutada')).toBeTruthy()
  })

  it('stops at the first failing line and says which one', async () => {
    seed([{ ...park, gcode: 'G0 Z5\nG99\nG0 X0' }])
    sendGcode.mockResolvedValueOnce({}).mockRejectedValueOnce(new Error("Error invoking remote method 'machine:gcode': Error: bad code"))
    render(<MacrosPanel />)
    fireEvent.click(screen.getByRole('button', { name: 'Aparcar' }))
    expect((await screen.findByRole('alert')).textContent).toBe('Línea 2 (G99): bad code')
    expect(sendGcode).toHaveBeenCalledTimes(2)
  })

  it('asks for confirmation first and does nothing when it is declined', () => {
    seed([{ ...park, confirm: true }])
    window.confirm = vi.fn(() => false)
    render(<MacrosPanel />)
    fireEvent.click(screen.getByRole('button', { name: 'Aparcar' }))
    expect(window.confirm).toHaveBeenCalledTimes(1)
    expect(vi.mocked(window.confirm).mock.calls[0][0]).toContain('G0 Z5')
    expect(sendGcode).not.toHaveBeenCalled()
  })

  it('does not ask when the macro does not require confirmation', async () => {
    seed([park])
    render(<MacrosPanel />)
    fireEvent.click(screen.getByRole('button', { name: 'Aparcar' }))
    await waitFor(() => expect(sendGcode).toHaveBeenCalled())
    expect(window.confirm).not.toHaveBeenCalled()
  })

  it('refuses a macro with no G-code lines', async () => {
    seed([{ ...park, gcode: '; nothing\n\n' }])
    render(<MacrosPanel />)
    fireEvent.click(screen.getByRole('button', { name: 'Aparcar' }))
    expect((await screen.findByRole('alert')).textContent).toContain('no tiene líneas')
    expect(sendGcode).not.toHaveBeenCalled()
  })

  it.each(['ESTOP', 'OFF', 'RUNNING', 'PAUSED', 'UNAVAILABLE'])('disables running in %s', state => {
    seed([park])
    setState(state)
    render(<MacrosPanel />)
    expect((screen.getByRole('button', { name: 'Aparcar' }) as HTMLButtonElement).disabled).toBe(true)
  })

  it('disables running while the status is stale', () => {
    seed([park])
    setState('IDLE', true)
    render(<MacrosPanel />)
    expect((screen.getByRole('button', { name: 'Aparcar' }) as HTMLButtonElement).disabled).toBe(true)
  })
})

describe('MacrosPanel editing', () => {
  it('adds a macro, edits it and saves it', () => {
    render(<MacrosPanel />)
    fireEvent.click(screen.getByRole('button', { name: 'Editar' }))
    fireEvent.click(screen.getByRole('button', { name: 'Añadir macro' }))
    fireEvent.change(screen.getByLabelText('Nombre de la macro'), { target: { value: 'Cero' } })
    fireEvent.change(screen.getByLabelText('G-code de la macro'), { target: { value: 'G92 X0' } })
    const saved = JSON.parse(window.localStorage.getItem('mcp-cnc.macros')!)
    expect(saved).toHaveLength(1)
    expect(saved[0]).toMatchObject({ name: 'Cero', gcode: 'G92 X0', confirm: true })
  })

  it('persists across a remount', () => {
    const first = render(<MacrosPanel />)
    fireEvent.click(screen.getByRole('button', { name: 'Editar' }))
    fireEvent.click(screen.getByRole('button', { name: 'Añadir macro' }))
    fireEvent.change(screen.getByLabelText('Nombre de la macro'), { target: { value: 'Cero' } })
    first.unmount()
    render(<MacrosPanel />)
    expect(screen.getByRole('button', { name: 'Cero' })).toBeTruthy()
  })

  it('toggles the confirmation requirement', () => {
    seed([park])
    render(<MacrosPanel />)
    fireEvent.click(screen.getByRole('button', { name: 'Editar' }))
    fireEvent.click(screen.getByLabelText('Confirmar antes de ejecutar'))
    expect(JSON.parse(window.localStorage.getItem('mcp-cnc.macros')!)[0].confirm).toBe(true)
  })

  it('deletes a macro', () => {
    seed([park])
    render(<MacrosPanel />)
    fireEvent.click(screen.getByRole('button', { name: 'Editar' }))
    fireEvent.click(screen.getByRole('button', { name: 'Borrar Aparcar' }))
    expect(JSON.parse(window.localStorage.getItem('mcp-cnc.macros')!)).toEqual([])
  })

  it('hides the run buttons while editing, so editing never fires a macro', () => {
    seed([park])
    render(<MacrosPanel />)
    fireEvent.click(screen.getByRole('button', { name: 'Editar' }))
    expect(screen.queryByRole('button', { name: 'Aparcar' })).toBeNull()
  })
})
