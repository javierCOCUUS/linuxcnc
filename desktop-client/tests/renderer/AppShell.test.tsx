import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, act, waitFor } from '@testing-library/react'

type FakeApi = ReturnType<typeof makeApi>

const h = vi.hoisted(() => ({
  apis: [] as unknown[],
  fromJSONThrows: false,
  fromJSONAddsPanel: true,
}))

function makeApi() {
  const panels = new Map<string, { id: string; api: { setActive: ReturnType<typeof vi.fn> } }>()
  const add = (id: string) => {
    const panel = { id, api: { setActive: vi.fn() } }
    panels.set(id, panel)
    return panel
  }
  return {
    addPanel: vi.fn((opts: { id: string }) => add(opts.id)),
    getPanel: vi.fn((id: string) => panels.get(id)),
    clear: vi.fn(() => panels.clear()),
    fromJSON: vi.fn(() => {
      if (h.fromJSONThrows) throw new Error('corrupt layout')
      if (h.fromJSONAddsPanel) add('machine-status')
    }),
    toJSON: vi.fn(() => ({ panels: [] })),
    onDidLayoutChange: vi.fn(() => ({ dispose: vi.fn() })),
    groups: [],
    get panels() { return Array.from(panels.values()) },
  }
}

vi.mock('dockview', async () => {
  const React = await import('react')
  return {
    DockviewReact: ({ onReady }: { onReady: (e: unknown) => void }) => {
      const done = React.useRef(false)
      if (!done.current) {
        done.current = true
        const api = makeApi()
        h.apis.push(api)
        onReady({ api })
      }
      return <div data-testid="dockview-mock" />
    },
  }
})

const mockElectronAPI = {
  getRole: vi.fn().mockResolvedValue({ role: 'machine', operatorEnabled: false }),
  listFiles: vi.fn().mockResolvedValue([]),
  layoutSave: vi.fn().mockResolvedValue(undefined),
  layoutLoad: vi.fn().mockResolvedValue(null),
  logout: vi.fn().mockResolvedValue(undefined),
  setEstop: vi.fn().mockResolvedValue({ status: 'estop_on' }),
}
Object.defineProperty(window, 'electronAPI', { value: mockElectronAPI, writable: true })

import { AppShell } from '../../src/renderer/src/components/AppShell'

function lastApi(): FakeApi {
  return h.apis[h.apis.length - 1] as FakeApi
}

async function renderShell(onLogout = vi.fn()): Promise<void> {
  await act(async () => {
    render(<AppShell userId="42" userName="Javier" onLogout={onLogout} />)
  })
}

async function openTab(name: string): Promise<void> {
  await act(async () => { fireEvent.click(screen.getByRole('tab', { name })) })
}

beforeEach(() => {
  vi.clearAllMocks()
  h.apis.length = 0
  h.fromJSONThrows = false
  h.fromJSONAddsPanel = true
  mockElectronAPI.layoutLoad.mockResolvedValue(null)
  mockElectronAPI.layoutSave.mockResolvedValue(undefined)
  mockElectronAPI.logout.mockResolvedValue(undefined)
  mockElectronAPI.setEstop.mockResolvedValue({ status: 'estop_on' })
  mockElectronAPI.getRole.mockResolvedValue({ role: 'machine', operatorEnabled: false })
  mockElectronAPI.listFiles.mockResolvedValue([])
})

describe('AppShell', () => {
  it('renders one tab per standard view', async () => {
    await renderShell()
    for (const name of ['Operación', 'Puesta en marcha', 'Diagnóstico', 'Producción', 'CAM']) {
      expect(screen.getByRole('tab', { name })).toBeTruthy()
    }
  })

  it('renders the dockview workspace area on a workspace tab', async () => {
    await renderShell()
    await openTab('Puesta en marcha')
    expect(screen.getByTestId('dockview-mock')).toBeTruthy()
  })

  it('shows the user name in the header', async () => {
    await renderShell()
    expect(screen.getByText('Javier')).toBeTruthy()
  })

  it('renders the Add panel button on a workspace tab', async () => {
    await renderShell()
    await openTab('Puesta en marcha')
    expect(screen.getByRole('button', { name: 'Add panel' })).toBeTruthy()
  })

  it('calls window.electronAPI.logout and onLogout when Logout is clicked', async () => {
    const onLogout = vi.fn()
    await renderShell(onLogout)
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Logout' }))
    })
    expect(mockElectronAPI.logout).toHaveBeenCalled()
    expect(onLogout).toHaveBeenCalled()
  })

  it('adds a new workspace tab, built from the commissioning template, when + is clicked', async () => {
    await renderShell()
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'New workspace' }))
    })
    expect(screen.getAllByRole('tab', { name: 'Puesta en marcha' })).toHaveLength(2)
    expect(lastApi().addPanel).toHaveBeenCalledTimes(3)
  })
})

describe('AppShell header', () => {
  it('has an emergency stop that is always available', async () => {
    await renderShell()
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Emergency stop' }))
    })
    expect(mockElectronAPI.setEstop).toHaveBeenCalledWith(true)
  })

  it('keeps the emergency stop when switching tabs', async () => {
    await renderShell()
    await act(async () => { fireEvent.click(screen.getByRole('tab', { name: 'CAM' })) })
    expect(screen.getByRole('button', { name: 'Emergency stop' })).toBeTruthy()
  })
})

describe('AppShell layouts', () => {
  it('builds a workspace tab from its template when nothing is saved', async () => {
    await renderShell()
    await openTab('Puesta en marcha')
    const added = lastApi().addPanel.mock.calls.map(c => (c[0] as { id: string }).id)
    expect(added).toEqual(['io-inputs', 'jog-control', 'machine-status'])
  })

  it('builds the template of whichever tab is opened', async () => {
    await renderShell()
    await act(async () => { fireEvent.click(screen.getByRole('tab', { name: 'Diagnóstico' })) })
    const added = lastApi().addPanel.mock.calls.map(c => (c[0] as { id: string }).id)
    expect(added).toEqual(['diagnostic', 'io-inputs', 'services', 'alarms'])
  })

  it('Reset layout clears the tab and rebuilds its template', async () => {
    await renderShell()
    await openTab('Puesta en marcha')
    const api = lastApi()
    api.addPanel.mockClear()
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Reset layout' })) })
    expect(api.clear).toHaveBeenCalledTimes(1)
    expect(api.addPanel.mock.calls.map(c => (c[0] as { id: string }).id))
      .toEqual(['io-inputs', 'jog-control', 'machine-status'])
  })

  it('restores a saved layout instead of rebuilding the template', async () => {
    mockElectronAPI.layoutLoad.mockResolvedValue({
      version: 2, userId: '42', activeTabId: 'saved',
      tabs: [{ id: 'saved', label: 'Mine', template: 'cam', dockviewState: { grid: 1 } }],
    })
    await renderShell()
    await waitFor(() => expect(screen.getByRole('tab', { name: 'Mine' })).toBeTruthy())
    const api = lastApi()
    expect(api.fromJSON).toHaveBeenCalledWith({ grid: 1 })
    expect(api.addPanel).not.toHaveBeenCalled()
  })

  it('falls back to the template when a saved layout cannot be restored', async () => {
    h.fromJSONThrows = true
    mockElectronAPI.layoutLoad.mockResolvedValue({
      version: 2, userId: '42', activeTabId: 'saved',
      tabs: [{ id: 'saved', label: 'Mine', template: 'cam', dockviewState: { broken: true } }],
    })
    await renderShell()
    await waitFor(() => expect(screen.getByRole('tab', { name: 'Mine' })).toBeTruthy())
    const api = lastApi()
    expect(api.addPanel.mock.calls.map(c => (c[0] as { id: string }).id))
      .toEqual(['dxf-cam', 'visualizer', 'gcode-editor'])
  })

  it('rebuilds the template when a saved layout restores with no panels', async () => {
    h.fromJSONAddsPanel = false
    mockElectronAPI.layoutLoad.mockResolvedValue({
      version: 2, userId: '42', activeTabId: 'saved',
      tabs: [{ id: 'saved', label: 'Mine', template: 'produccion', dockviewState: { empty: true } }],
    })
    await renderShell()
    await waitFor(() => expect(screen.getByRole('tab', { name: 'Mine' })).toBeTruthy())
    expect(lastApi().addPanel.mock.calls.map(c => (c[0] as { id: string }).id))
      .toEqual(['machine-status', 'file-manager', 'position-xyz'])
  })
})

describe('AppShell Add panel', () => {
  beforeEach(async () => {
    await renderShell()
    await openTab('Puesta en marcha')
  })

  async function pick(title: string): Promise<void> {
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Add panel' })) })
    await act(async () => { fireEvent.click(screen.getByText(title)) })
  }

  it('focuses a panel the tab already has instead of duplicating it', async () => {
    const api = lastApi()
    api.addPanel.mockClear()
    await pick('Jog Control')
    expect(api.addPanel).not.toHaveBeenCalled()
    expect(api.getPanel('jog-control')!.api.setActive).toHaveBeenCalledTimes(1)
  })

  it('adds a panel the tab does not have', async () => {
    const api = lastApi()
    api.addPanel.mockClear()
    await pick('Alarmas')
    expect(api.addPanel).toHaveBeenCalledTimes(1)
    expect(api.addPanel.mock.calls[0][0]).toMatchObject({ id: 'alarms', component: 'alarms' })
  })

  it('opens a panel only once however many times it is picked', async () => {
    const api = lastApi()
    api.addPanel.mockClear()
    await pick('Services')
    await pick('Services')
    await pick('Services')
    expect(api.addPanel).toHaveBeenCalledTimes(1)
  })

  it('the settings button opens the settings panel on a workspace tab', async () => {
    const api = lastApi()
    api.addPanel.mockClear()
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Settings' })) })
    expect(api.addPanel.mock.calls[0][0]).toMatchObject({ id: 'config' })
  })
})

describe('AppShell Operation screen', () => {
  it('opens on the fixed Operation screen, with its cards and no dockview', async () => {
    await renderShell()
    for (const card of ['Posición', 'Programa', 'Ciclo', 'Avance y spindle', 'Husillo', 'Jog', 'Macros', 'Herramienta y ceros']) {
      expect(screen.getByRole('region', { name: card })).toBeTruthy()
    }
    expect(screen.queryByTestId('dockview-mock')).toBeNull()
  })

  it('hides Add panel and disables Reset layout on the screen', async () => {
    await renderShell()
    expect(screen.queryByRole('button', { name: 'Add panel' })).toBeNull()
    expect((screen.getByRole('button', { name: 'Reset layout' }) as HTMLButtonElement).disabled).toBe(true)
  })

  it('brings Add panel back on a workspace tab', async () => {
    await renderShell()
    await openTab('Diagnóstico')
    expect(screen.getByRole('button', { name: 'Add panel' })).toBeTruthy()
    expect((screen.getByRole('button', { name: 'Reset layout' }) as HTMLButtonElement).disabled).toBe(false)
  })

  it('the settings button leaves the screen for a workspace tab and opens Settings there', async () => {
    await renderShell()
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Settings' })) })
    expect(screen.getByTestId('dockview-mock')).toBeTruthy()
    expect(lastApi().getPanel('config')).toBeTruthy()
  })

  it('keeps the emergency stop on the screen', async () => {
    await renderShell()
    expect(screen.getByRole('button', { name: 'Emergency stop' })).toBeTruthy()
  })
})

describe('AppShell roles', () => {
  it('shows no operator badge for the machine role', async () => {
    await renderShell()
    await waitFor(() => expect(mockElectronAPI.getRole).toHaveBeenCalled())
    expect(screen.queryByText('MODO OPERADOR')).toBeNull()
  })

  it('shows the operator badge and disables machine-moving buttons for the operator role', async () => {
    mockElectronAPI.getRole.mockResolvedValue({ role: 'operator', operatorEnabled: true })
    await renderShell()
    expect(await screen.findByText('MODO OPERADOR')).toBeTruthy()
    expect((screen.getByRole('button', { name: 'Jog X+' }) as HTMLButtonElement).disabled).toBe(true)
    expect((screen.getByRole('button', { name: 'Emergency stop' }) as HTMLButtonElement).disabled).toBe(false)
  })

  it('keeps the machine-moving buttons off until the role is known', async () => {
    mockElectronAPI.getRole.mockReturnValue(new Promise(() => {}))
    await renderShell()
    expect((screen.getByRole('button', { name: 'Jog X+' }) as HTMLButtonElement).disabled).toBe(true)
  })
})
