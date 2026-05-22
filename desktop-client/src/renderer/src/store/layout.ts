import { useState, useCallback } from 'react'
import type { WorkspaceLayout } from '../types/layout'

let tabCounter = 0
function newTabId(): string {
  return `tab-${Date.now()}-${++tabCounter}`
}

function makeDefaultLayout(userId: string): WorkspaceLayout {
  const tabId = newTabId()
  return {
    version: 1,
    userId,
    tabs: [{ id: tabId, label: 'Workspace 1', dockviewState: null }],
    activeTabId: tabId,
  }
}

function save(layout: WorkspaceLayout): void {
  window.electronAPI.layoutSave(layout)
}

export function useLayoutStore(userId: string) {
  const [layout, setLayout] = useState<WorkspaceLayout>(() => makeDefaultLayout(userId))

  const loadLayout = useCallback(async () => {
    const saved = await window.electronAPI.layoutLoad(userId)
    if (saved) setLayout(saved as WorkspaceLayout)
  }, [userId])

  const addTab = useCallback(() => {
    setLayout(prev => {
      const id = newTabId()
      const next: WorkspaceLayout = {
        ...prev,
        tabs: [...prev.tabs, { id, label: 'New workspace', dockviewState: null }],
        activeTabId: id,
      }
      save(next)
      return next
    })
  }, [])

  const removeTab = useCallback((tabId: string) => {
    setLayout(prev => {
      if (prev.tabs.length <= 1) return prev
      const tabs = prev.tabs.filter(t => t.id !== tabId)
      const activeTabId = prev.activeTabId === tabId ? tabs[0].id : prev.activeTabId
      const next: WorkspaceLayout = { ...prev, tabs, activeTabId }
      save(next)
      return next
    })
  }, [])

  const renameTab = useCallback((tabId: string, label: string) => {
    setLayout(prev => {
      const next: WorkspaceLayout = {
        ...prev,
        tabs: prev.tabs.map(t => t.id === tabId ? { ...t, label } : t),
      }
      save(next)
      return next
    })
  }, [])

  const setActiveTab = useCallback((tabId: string) => {
    setLayout(prev => {
      if (prev.activeTabId === tabId) return prev
      const next = { ...prev, activeTabId: tabId }
      save(next)
      return next
    })
  }, [])

  const updateTabDockview = useCallback((tabId: string, dockviewState: object) => {
    setLayout(prev => {
      const next: WorkspaceLayout = {
        ...prev,
        tabs: prev.tabs.map(t => t.id === tabId ? { ...t, dockviewState } : t),
      }
      save(next)
      return next
    })
  }, [])

  return { layout, loadLayout, addTab, removeTab, renameTab, setActiveTab, updateTabDockview }
}
