import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'

vi.mock('../../src/renderer/src/context/MachineDataContext', () => ({
  useMachineData: vi.fn(),
}))
vi.mock('../../src/renderer/src/context/RoleContext', () => ({
  useRole: vi.fn(),
}))

import { ProgramPanel, CycleControls } from '../../src/renderer/src/components/panels/ProgramPanel'
import { useMachineData } from '../../src/renderer/src/context/MachineDataContext'
import { useRole } from '../../src/renderer/src/context/RoleContext'

const mockUseMachineData = vi.mocked(useMachineData)
const mockUseRole = vi.mocked(useRole)
const programCommand = vi.fn()
const listFiles = vi.fn()

function setStatus(state: string, stale = false): void {
  mockUseMachineData.mockReturnValue({ data: { state } as never, error: null, stale, loading: false })
}
const button = (name: string | RegExp): HTMLButtonElement => screen.getByRole('button', { name }) as HTMLButtonElement

beforeEach(() => {
  vi.clearAllMocks()
  programCommand.mockResolvedValue({ status: 'ok' })
  listFiles.mockResolvedValue([{ name: 'tapa.tap', size: 10, modified: 0 }, { name: 'caja.nc', size: 10, modified: 0 }])
  window.electronAPI = { programCommand, listFiles } as unknown as typeof window.electronAPI
  window.confirm = vi.fn(() => true)
  mockUseRole.mockReturnValue('machine')
  setStatus('IDLE')
})

describe('CycleControls', () => {
  it('cannot start a program that was not opened from this screen', () => {
    render(<CycleControls openedFile={null} />)
    expect(button('CYCLE START').disabled).toBe(true)
  })

  it('starts only after asking for confirmation, naming the file', async () => {
    render(<CycleControls openedFile="tapa.tap" />)
    fireEvent.click(button('CYCLE START'))
    expect(window.confirm).toHaveBeenCalledWith('¿Iniciar «tapa.tap»?')
    await waitFor(() => expect(programCommand).toHaveBeenCalledWith({ action: 'run' }))
  })

  it('does not start when the confirmation is declined', () => {
    window.confirm = vi.fn(() => false)
    render(<CycleControls openedFile="tapa.tap" />)
    fireEvent.click(button('CYCLE START'))
    expect(programCommand).not.toHaveBeenCalled()
  })

  it.each(['ESTOP', 'OFF', 'RUNNING', 'PAUSED', 'MDI', 'UNAVAILABLE'])('cannot start in %s', state => {
    setStatus(state)
    render(<CycleControls openedFile="tapa.tap" />)
    expect(button('CYCLE START').disabled).toBe(true)
  })

  it('cannot start while the status is stale', () => {
    setStatus('IDLE', true)
    render(<CycleControls openedFile="tapa.tap" />)
    expect(button('CYCLE START').disabled).toBe(true)
  })

  it('an operator cannot start, but can pause and stop', () => {
    mockUseRole.mockReturnValue('operator')
    setStatus('RUNNING')
    render(<CycleControls openedFile="tapa.tap" />)
    expect(button('CYCLE START').disabled).toBe(true)
    expect(button('FEED HOLD').disabled).toBe(false)
    expect(button('STOP').disabled).toBe(false)
  })

  it('FEED HOLD is only available while running, and pauses', async () => {
    setStatus('IDLE')
    const idle = render(<CycleControls openedFile="a" />)
    expect(button('FEED HOLD').disabled).toBe(true)
    idle.unmount()
    setStatus('RUNNING')
    render(<CycleControls openedFile="a" />)
    fireEvent.click(button('FEED HOLD'))
    await waitFor(() => expect(programCommand).toHaveBeenCalledWith({ action: 'pause' }))
  })

  it('while paused the button resumes, and only the machine role may do it', async () => {
    setStatus('PAUSED')
    const machine = render(<CycleControls openedFile="a" />)
    fireEvent.click(button('RESUME'))
    await waitFor(() => expect(programCommand).toHaveBeenCalledWith({ action: 'resume' }))
    machine.unmount()
    mockUseRole.mockReturnValue('operator')
    render(<CycleControls openedFile="a" />)
    expect(button('RESUME').disabled).toBe(true)
  })

  it('STOP is always enabled, in every state, role and with a stale status', async () => {
    for (const state of ['ESTOP', 'OFF', 'IDLE', 'RUNNING', 'PAUSED', 'UNAVAILABLE']) {
      for (const role of ['machine', 'operator'] as const) {
        mockUseRole.mockReturnValue(role)
        setStatus(state, true)
        const { unmount } = render(<CycleControls openedFile={null} />)
        expect(button('STOP').disabled).toBe(false)
        unmount()
      }
    }
  })

  it('STOP sends stop', async () => {
    render(<CycleControls openedFile={null} />)
    fireEvent.click(button('STOP'))
    await waitFor(() => expect(programCommand).toHaveBeenCalledWith({ action: 'stop' }))
  })

  it('shows why a command was refused, without the Electron prefix', async () => {
    programCommand.mockRejectedValue(new Error("Error invoking remote method 'machine:program': Error: LinuxCNC is in E-stop"))
    setStatus('RUNNING')
    render(<CycleControls openedFile="a" />)
    fireEvent.click(button('FEED HOLD'))
    expect((await screen.findByRole('alert')).textContent).toBe('LinuxCNC is in E-stop')
  })
})

describe('ProgramPanel', () => {
  it('lists the files of the workspace', async () => {
    render(<ProgramPanel />)
    expect(await screen.findByRole('option', { name: 'tapa.tap' })).toBeTruthy()
    expect(screen.getByRole('option', { name: 'caja.nc' })).toBeTruthy()
  })

  it('offers only G-code files, not folders or other files from the workspace', async () => {
    listFiles.mockResolvedValue([
      { name: 'designs', size: 4096, modified: 0 },
      { name: 'tapa.tap', size: 1, modified: 0 },
      { name: 'plano.dxf', size: 1, modified: 0 },
      { name: 'LATERAL.NGC', size: 1, modified: 0 },
      { name: 'notas.txt', size: 1, modified: 0 },
      { name: 'foto.png', size: 1, modified: 0 },
      { name: 'pieza.gcode', size: 1, modified: 0 },
    ])
    render(<ProgramPanel />)
    await screen.findByRole('option', { name: 'tapa.tap' })
    const names = screen.getAllByRole('option').map(o => o.textContent)
    expect(names).toEqual(['Elige un archivo', 'tapa.tap', 'LATERAL.NGC', 'notas.txt', 'pieza.gcode'])
  })

  it('says there are no files when the workspace has none that are G-code', async () => {
    listFiles.mockResolvedValue([{ name: 'designs', size: 4096, modified: 0 }])
    render(<ProgramPanel />)
    expect(await screen.findByRole('option', { name: 'No hay archivos' })).toBeTruthy()
  })

  it('says there are no files', async () => {
    listFiles.mockResolvedValue([])
    render(<ProgramPanel />)
    expect(await screen.findByRole('option', { name: 'No hay archivos' })).toBeTruthy()
  })

  it('cannot load until a file is chosen', async () => {
    render(<ProgramPanel />)
    await screen.findByRole('option', { name: 'tapa.tap' })
    expect(button('CARGAR').disabled).toBe(true)
    fireEvent.change(screen.getByLabelText('Archivo de G-code'), { target: { value: 'tapa.tap' } })
    expect(button('CARGAR').disabled).toBe(false)
  })

  it('opens the chosen file and then allows rewind and single step', async () => {
    render(<ProgramPanel showCycle={false} />)
    await screen.findByRole('option', { name: 'tapa.tap' })
    expect(button('REWIND').disabled).toBe(true)
    fireEvent.change(screen.getByLabelText('Archivo de G-code'), { target: { value: 'tapa.tap' } })
    fireEvent.click(button('CARGAR'))
    await waitFor(() => expect(programCommand).toHaveBeenCalledWith({ action: 'open', filename: 'tapa.tap' }))
    expect(await screen.findByText('tapa.tap', { selector: 'strong' })).toBeTruthy()
    expect(button('REWIND').disabled).toBe(false)
    fireEvent.click(button('LÍNEA A LÍNEA'))
    await waitFor(() => expect(programCommand).toHaveBeenCalledWith({ action: 'step' }))
  })

  it('shows the cycle controls by default and can hide them', async () => {
    const withCycle = render(<ProgramPanel />)
    expect(screen.getByRole('button', { name: 'CYCLE START' })).toBeTruthy()
    withCycle.unmount()
    render(<ProgramPanel showCycle={false} />)
    expect(screen.queryByRole('button', { name: 'CYCLE START' })).toBeNull()
  })

  it('shares the opened file with a separate CycleControls when it is controlled', async () => {
    const onOpened = vi.fn()
    render(<ProgramPanel showCycle={false} opened="tapa.tap" onOpened={onOpened} />)
    expect(screen.getByText('tapa.tap', { selector: 'strong' })).toBeTruthy()
    await screen.findByRole('option', { name: 'caja.nc' })
    fireEvent.change(screen.getByLabelText('Archivo de G-code'), { target: { value: 'caja.nc' } })
    fireEvent.click(button('CARGAR'))
    await waitFor(() => expect(onOpened).toHaveBeenCalledWith('caja.nc'))
  })

  it.each(['ESTOP', 'OFF', 'RUNNING', 'PAUSED', 'UNAVAILABLE'])('cannot load a file in %s', async state => {
    setStatus(state)
    render(<ProgramPanel showCycle={false} />)
    await screen.findByRole('option', { name: 'tapa.tap' })
    fireEvent.change(screen.getByLabelText('Archivo de G-code'), { target: { value: 'tapa.tap' } })
    expect(button('CARGAR').disabled).toBe(true)
  })

  it('an operator cannot load, rewind or step', async () => {
    mockUseRole.mockReturnValue('operator')
    render(<ProgramPanel showCycle={false} opened="tapa.tap" onOpened={vi.fn()} />)
    await screen.findByRole('option', { name: 'tapa.tap' })
    fireEvent.change(screen.getByLabelText('Archivo de G-code'), { target: { value: 'tapa.tap' } })
    for (const name of ['CARGAR', 'REWIND', 'LÍNEA A LÍNEA']) expect(button(name).disabled).toBe(true)
  })

  it('shows why a file could not be loaded', async () => {
    programCommand.mockRejectedValue(new Error("Error invoking remote method 'machine:program': Error: LINUXCNC_REMOTE_GCODE_DIR is not configured"))
    render(<ProgramPanel showCycle={false} />)
    await screen.findByRole('option', { name: 'tapa.tap' })
    fireEvent.change(screen.getByLabelText('Archivo de G-code'), { target: { value: 'tapa.tap' } })
    fireEvent.click(button('CARGAR'))
    expect((await screen.findByRole('alert')).textContent).toContain('LINUXCNC_REMOTE_GCODE_DIR')
    expect(screen.queryByText('tapa.tap', { selector: 'strong' })).toBeNull()
  })

  it('reports a failure to list the files', async () => {
    listFiles.mockRejectedValue(new Error('HTTP 403'))
    render(<ProgramPanel />)
    expect((await screen.findByRole('alert')).textContent).toBe('HTTP 403')
  })
})
