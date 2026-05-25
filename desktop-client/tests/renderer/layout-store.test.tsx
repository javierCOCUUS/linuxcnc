import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'

const mockElectronAPI = {
  layoutSave: vi.fn().mockResolvedValue(undefined),
  layoutLoad: vi.fn().mockResolvedValue(null),
}

Object.defineProperty(window, 'electronAPI', {
  value: mockElectronAPI,
  writable: true,
})

import { useLayoutStore } from '../../src/renderer/src/store/layout'

beforeEach(() => {
  vi.clearAllMocks()
  mockElectronAPI.layoutLoad.mockResolvedValue(null)
  mockElectronAPI.layoutSave.mockResolvedValue(undefined)
})

describe('useLayoutStore', () => {
  it('initializes with one default tab for the given userId', () => {
    const { result } = renderHook(() => useLayoutStore('user-1'))
    expect(result.current.layout.userId).toBe('user-1')
    expect(result.current.layout.tabs).toHaveLength(1)
    expect(result.current.layout.tabs[0].label).toBe('Workspace 1')
    expect(result.current.layout.tabs[0].dockviewState).toBeNull()
    expect(result.current.layout.activeTabId).toBe(result.current.layout.tabs[0].id)
  })

  it('addTab appends a new tab and activates it', async () => {
    const { result } = renderHook(() => useLayoutStore('user-1'))
    await act(async () => { result.current.addTab() })
    expect(result.current.layout.tabs).toHaveLength(2)
    expect(result.current.layout.activeTabId).toBe(result.current.layout.tabs[1].id)
    expect(result.current.layout.tabs[1].label).toBe('New workspace')
    expect(mockElectronAPI.layoutSave).toHaveBeenCalled()
  })

  it('removeTab removes the given tab and keeps at least one tab', async () => {
    const { result } = renderHook(() => useLayoutStore('user-1'))
    await act(async () => { result.current.addTab() })
    const idToRemove = result.current.layout.tabs[1].id
    await act(async () => { result.current.removeTab(idToRemove) })
    expect(result.current.layout.tabs).toHaveLength(1)
    expect(result.current.layout.tabs.find(t => t.id === idToRemove)).toBeUndefined()
  })

  it('removeTab does nothing when only one tab remains', async () => {
    const { result } = renderHook(() => useLayoutStore('user-1'))
    const onlyId = result.current.layout.tabs[0].id
    await act(async () => { result.current.removeTab(onlyId) })
    expect(result.current.layout.tabs).toHaveLength(1)
  })

  it('removeTab activates the first remaining tab when the active tab is removed', async () => {
    const { result } = renderHook(() => useLayoutStore('user-1'))
    await act(async () => { result.current.addTab() })
    const activeId = result.current.layout.tabs[1].id
    await act(async () => { result.current.setActiveTab(activeId) })
    await act(async () => { result.current.removeTab(activeId) })
    expect(result.current.layout.activeTabId).toBe(result.current.layout.tabs[0].id)
  })

  it('renameTab updates the label of the given tab', async () => {
    const { result } = renderHook(() => useLayoutStore('user-1'))
    const id = result.current.layout.tabs[0].id
    await act(async () => { result.current.renameTab(id, 'Mecanizado') })
    expect(result.current.layout.tabs[0].label).toBe('Mecanizado')
    expect(mockElectronAPI.layoutSave).toHaveBeenCalled()
  })

  it('setActiveTab changes the activeTabId', async () => {
    const { result } = renderHook(() => useLayoutStore('user-1'))
    await act(async () => { result.current.addTab() })
    const secondId = result.current.layout.tabs[1].id
    await act(async () => { result.current.setActiveTab(secondId) })
    expect(result.current.layout.activeTabId).toBe(secondId)
  })

  it('updateTabDockview persists the dockview serialized state', async () => {
    const { result } = renderHook(() => useLayoutStore('user-1'))
    const id = result.current.layout.tabs[0].id
    const dockState = { panels: [{ id: 'p1' }] }
    await act(async () => { result.current.updateTabDockview(id, dockState) })
    expect(result.current.layout.tabs[0].dockviewState).toEqual(dockState)
    expect(mockElectronAPI.layoutSave).toHaveBeenCalled()
  })

  it('loadLayout replaces state with the saved layout when one exists', async () => {
    const saved = {
      version: 1 as const,
      userId: 'user-1',
      tabs: [{ id: 'saved-tab', label: 'Saved', dockviewState: null }],
      activeTabId: 'saved-tab',
    }
    mockElectronAPI.layoutLoad.mockResolvedValue(saved)
    const { result } = renderHook(() => useLayoutStore('user-1'))
    await act(async () => { await result.current.loadLayout() })
    expect(result.current.layout.tabs[0].id).toBe('saved-tab')
  })
})
