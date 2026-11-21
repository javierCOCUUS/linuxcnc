import { useState, useCallback } from 'react'
import type { TemplateId, WorkspaceLayout } from '../types/layout'
import { DEFAULT_TEMPLATE, TEMPLATES, getTemplate } from '../lib/templates'

let tabCounter = 0
function newTabId(): string {
  return `tab-${Date.now()}-${++tabCounter}`
}

// One tab per template, so a fresh install opens on the five standard views.
function makeDefaultLayout(userId: string): WorkspaceLayout {
  const tabs = TEMPLATES.map(t => ({
    id: newTabId(),
    label: t.label,
    template: t.id,
    dockviewState: null,
  }))
  return { version: 2, userId, tabs, activeTabId: tabs[0].id }
}

function save(layout: WorkspaceLayout): void {
  window.electronAPI.layoutSave(layout)
}

export function useLayoutStore(userId: string) {
  const [layout, setLayout] = useState<WorkspaceLayout>(() => makeDefaultLayout(userId))

  const loadLayout = useCallback(async () => {
    const saved = await window.electronAPI.layoutLoad(userId)
    // Layouts saved by older versions (no templates, built without the dockview
    // stylesheet) are dropped in favour of the default tabs.
    if (saved && (saved as { version?: number }).version === 2) {
      setLayout(saved as WorkspaceLayout)
    }
  }, [userId])

  const addTab = useCallback((template: TemplateId = DEFAULT_TEMPLATE) => {
    setLayout(prev => {
      const id = newTabId()
      const next: WorkspaceLayout = {
        ...prev,
        tabs: [...prev.tabs, { id, label: getTemplate(template).label, template, dockviewState: null }],
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
