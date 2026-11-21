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

  describe('saved layouts that cannot be trusted', () => {
    const goodTab = { id: 'a', label: 'Mine', template: 'cam', dockviewState: null }
    const layoutWith = (over: object) => ({ version: 2, userId: 'user-1', activeTabId: 'a', tabs: [goodTab], ...over })

    async function load(saved: unknown) {
      mockElectronAPI.layoutLoad.mockResolvedValue(saved)
      const hook = renderHook(() => useLayoutStore('user-1'))
      await act(async () => { await hook.result.current.loadLayout() })
      return hook
    }

    it.each([
      ['tabs without a template (the tabs of an older version)', layoutWith({ tabs: [{ id: 'a', label: 'Setup', dockviewState: null }] })],
      ['a tab with an unknown template', layoutWith({ tabs: [{ ...goodTab, template: 'nope' }] })],
      ['no tabs', layoutWith({ tabs: [] })],
      ['tabs that are not a list', layoutWith({ tabs: 'x' })],
      ['duplicate tab ids', layoutWith({ tabs: [goodTab, { ...goodTab, label: 'Other' }] })],
      ['a layout state that is not an object', layoutWith({ tabs: [{ ...goodTab, dockviewState: 'garbage' }] })],
      ['a tab without an id', layoutWith({ tabs: [{ ...goodTab, id: '' }] })],
      ['a tab without a label', layoutWith({ tabs: [{ ...goodTab, label: 5 }] })],
      ['an old version', layoutWith({ version: 1 })],
      ['a value that is not an object', 'text'],
    ])('discards %s and keeps the five default tabs', async (_name, saved) => {
      const { result } = await load(saved)
      expect(result.current.layout.tabs.map(t => t.label)).toEqual([
        'Operación', 'Puesta en marcha', 'Diagnóstico', 'Producción', 'CAM',
      ])
    })

    it('overwrites the stale file with the default tabs so it does not come back', async () => {
      await load(layoutWith({ tabs: [{ id: 'a', label: 'Setup', dockviewState: null }] }))
      expect(mockElectronAPI.layoutSave).toHaveBeenCalled()
      const written = mockElectronAPI.layoutSave.mock.calls.at(-1)![0]
      expect(written.version).toBe(2)
      expect(written.tabs).toHaveLength(5)
    })

    it('does not write anything when nothing was stored', async () => {
      await load(null)
      expect(mockElectronAPI.layoutSave).not.toHaveBeenCalled()
    })

    it('keeps a valid saved layout exactly as it is', async () => {
      const saved = layoutWith({ tabs: [goodTab, { id: 'b', label: 'Two', template: 'diagnostico', dockviewState: { grid: 1 } }] })
      const { result } = await load(saved)
      expect(result.current.layout.tabs).toEqual(saved.tabs)
      expect(mockElectronAPI.layoutSave).not.toHaveBeenCalled()
    })

    it('repairs an active tab id that no longer exists instead of dropping the tabs', async () => {
      const { result } = await load(layoutWith({ activeTabId: 'gone', tabs: [goodTab, { ...goodTab, id: 'b' }] }))
      expect(result.current.layout.tabs).toHaveLength(2)
      expect(result.current.layout.activeTabId).toBe('a')
    })
  })

  describe('resetTabs', () => {
    it('goes back to the five standard tabs and saves them', async () => {
      const { result } = renderHook(() => useLayoutStore('user-1'))
      await act(async () => { result.current.addTab() })
      await act(async () => { result.current.renameTab(result.current.layout.tabs[0].id, 'Custom') })
      expect(result.current.layout.tabs).toHaveLength(6)
      mockElectronAPI.layoutSave.mockClear()
      await act(async () => { result.current.resetTabs() })
      expect(result.current.layout.tabs.map(t => t.label)).toEqual([
        'Operación', 'Puesta en marcha', 'Diagnóstico', 'Producción', 'CAM',
      ])
      expect(result.current.layout.tabs.every(t => t.dockviewState === null)).toBe(true)
      expect(result.current.layout.activeTabId).toBe(result.current.layout.tabs[0].id)
      expect(result.current.layout.userId).toBe('user-1')
      expect(mockElectronAPI.layoutSave).toHaveBeenCalledTimes(1)
      expect(mockElectronAPI.layoutSave.mock.calls[0][0].tabs).toHaveLength(5)
    })
  })
})
