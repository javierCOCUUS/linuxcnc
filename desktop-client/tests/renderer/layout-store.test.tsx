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
  it('initializes with one tab per template for the given userId', () => {
    const { result } = renderHook(() => useLayoutStore('user-1'))
    const { layout } = result.current
    expect(layout.version).toBe(2)
    expect(layout.userId).toBe('user-1')
    expect(layout.tabs.map(t => t.label)).toEqual([
      'Operación', 'Puesta en marcha', 'Diagnóstico', 'Producción', 'CAM',
    ])
    expect(layout.tabs.map(t => t.template)).toEqual([
      'operacion', 'puesta-en-marcha', 'diagnostico', 'produccion', 'cam',
    ])
    expect(layout.tabs.every(t => t.dockviewState === null)).toBe(true)
    expect(layout.activeTabId).toBe(layout.tabs[0].id)
  })

  it('addTab appends a new tab and activates it', async () => {
    const { result } = renderHook(() => useLayoutStore('user-1'))
    await act(async () => { result.current.addTab() })
    const tabs = result.current.layout.tabs
    expect(tabs).toHaveLength(6)
    expect(result.current.layout.activeTabId).toBe(tabs[5].id)
    expect(tabs[5]).toMatchObject({ label: 'Puesta en marcha', template: 'puesta-en-marcha', dockviewState: null })
    expect(mockElectronAPI.layoutSave).toHaveBeenCalled()
  })

  it('addTab can start from another template', async () => {
    const { result } = renderHook(() => useLayoutStore('user-1'))
    await act(async () => { result.current.addTab('cam') })
    expect(result.current.layout.tabs[5]).toMatchObject({ label: 'CAM', template: 'cam' })
  })

  it('removeTab removes the given tab and keeps at least one tab', async () => {
    const { result } = renderHook(() => useLayoutStore('user-1'))
    const idToRemove = result.current.layout.tabs[1].id
    await act(async () => { result.current.removeTab(idToRemove) })
    expect(result.current.layout.tabs).toHaveLength(4)
    expect(result.current.layout.tabs.find(t => t.id === idToRemove)).toBeUndefined()
  })

  it('removeTab does nothing when only one tab remains', async () => {
    const { result } = renderHook(() => useLayoutStore('user-1'))
    for (let i = 0; i < 4; i++) {
      const id = result.current.layout.tabs[result.current.layout.tabs.length - 1].id
      await act(async () => { result.current.removeTab(id) })
    }
    expect(result.current.layout.tabs).toHaveLength(1)
    const onlyId = result.current.layout.tabs[0].id
    await act(async () => { result.current.removeTab(onlyId) })
    expect(result.current.layout.tabs).toHaveLength(1)
  })

  it('removeTab activates the first remaining tab when the active tab is removed', async () => {
    const { result } = renderHook(() => useLayoutStore('user-1'))
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
      version: 2 as const,
      userId: 'user-1',
      tabs: [{ id: 'saved-tab', label: 'Saved', template: 'cam', dockviewState: null }],
      activeTabId: 'saved-tab',
    }
    mockElectronAPI.layoutLoad.mockResolvedValue(saved)
    const { result } = renderHook(() => useLayoutStore('user-1'))
    await act(async () => { await result.current.loadLayout() })
    expect(result.current.layout.tabs[0].id).toBe('saved-tab')
  })

  it('loadLayout ignores a layout saved by an older version and keeps the default tabs', async () => {
    mockElectronAPI.layoutLoad.mockResolvedValue({
      version: 1,
      userId: 'user-1',
      tabs: [{ id: 'old-tab', label: 'Old', dockviewState: { panels: [] } }],
      activeTabId: 'old-tab',
    })
    const { result } = renderHook(() => useLayoutStore('user-1'))
    await act(async () => { await result.current.loadLayout() })
    expect(result.current.layout.tabs.find(t => t.id === 'old-tab')).toBeUndefined()
    expect(result.current.layout.tabs).toHaveLength(5)
  })
})
