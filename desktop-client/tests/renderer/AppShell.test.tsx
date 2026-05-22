import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, act } from '@testing-library/react'

vi.mock('dockview', () => ({
  DockviewReact: ({ onReady }: { onReady: (e: unknown) => void }) => {
    const api = {
      addPanel: vi.fn(),
      toJSON: vi.fn(() => ({ panels: [] })),
      fromJSON: vi.fn(),
      onDidLayoutChange: vi.fn(() => ({ dispose: vi.fn() })),
    }
    onReady({ api })
    return <div data-testid="dockview-mock" />
  },
}))

const mockElectronAPI = {
  layoutSave: vi.fn().mockResolvedValue(undefined),
  layoutLoad: vi.fn().mockResolvedValue(null),
  logout: vi.fn().mockResolvedValue(undefined),
}
Object.defineProperty(window, 'electronAPI', { value: mockElectronAPI, writable: true })

import { AppShell } from '../../src/renderer/src/components/AppShell'

beforeEach(() => {
  vi.clearAllMocks()
  mockElectronAPI.layoutLoad.mockResolvedValue(null)
  mockElectronAPI.layoutSave.mockResolvedValue(undefined)
  mockElectronAPI.logout.mockResolvedValue(undefined)
})

describe('AppShell', () => {
  it('renders the tab bar with the default workspace tab', async () => {
    await act(async () => {
      render(<AppShell userId="42" userName="Javier" onLogout={vi.fn()} />)
    })
    expect(screen.getByText('Workspace 1')).toBeInTheDocument()
  })

  it('renders the dockview workspace area', async () => {
    await act(async () => {
      render(<AppShell userId="42" userName="Javier" onLogout={vi.fn()} />)
    })
    expect(screen.getByTestId('dockview-mock')).toBeInTheDocument()
  })

  it('shows the user name in the header', async () => {
    await act(async () => {
      render(<AppShell userId="42" userName="Javier" onLogout={vi.fn()} />)
    })
    expect(screen.getByText('Javier')).toBeInTheDocument()
  })

  it('renders the Add panel button', async () => {
    await act(async () => {
      render(<AppShell userId="42" userName="Javier" onLogout={vi.fn()} />)
    })
    expect(screen.getByRole('button', { name: 'Add panel' })).toBeInTheDocument()
  })

  it('calls window.electronAPI.logout and onLogout when Logout is clicked', async () => {
    const onLogout = vi.fn()
    await act(async () => {
      render(<AppShell userId="42" userName="Javier" onLogout={onLogout} />)
    })
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Logout' }))
    })
    expect(mockElectronAPI.logout).toHaveBeenCalled()
    expect(onLogout).toHaveBeenCalled()
  })

  it('adds a new tab when the + button is clicked', async () => {
    await act(async () => {
      render(<AppShell userId="42" userName="Javier" onLogout={vi.fn()} />)
    })
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'New workspace' }))
    })
    expect(screen.getByText('New workspace')).toBeInTheDocument()
  })
})
