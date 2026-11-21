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

/**
 * Returns the saved layout when it can be trusted, or null. Every tab must have a known
 * template and a layout state that is an object or null; anything else (a file written by
 * an older version, or a damaged one) is discarded instead of half-loaded.
 */
export function validSavedLayout(saved: unknown): WorkspaceLayout | null {
  if (typeof saved !== 'object' || saved === null) return null
  const layout = saved as Partial<WorkspaceLayout>
  if (layout.version !== 2 || !Array.isArray(layout.tabs) || layout.tabs.length === 0) return null
  const templates: string[] = TEMPLATES.map(t => t.id)
  const tabsOk = layout.tabs.every(tab =>
    typeof tab === 'object' && tab !== null
    && typeof tab.id === 'string' && tab.id !== ''
    && typeof tab.label === 'string'
    && templates.includes(tab.template as string)
    && (tab.dockviewState === null || (typeof tab.dockviewState === 'object')))
  if (!tabsOk) return null
  const ids = layout.tabs.map(t => t.id)
  if (new Set(ids).size !== ids.length) return null
  // A dangling active tab is repaired rather than discarding the user's tabs.
  const activeTabId = ids.includes(layout.activeTabId as string) ? (layout.activeTabId as string) : ids[0]
  return { ...(layout as WorkspaceLayout), activeTabId }
}

export function useLayoutStore(userId: string) {
  const [layout, setLayout] = useState<WorkspaceLayout>(() => makeDefaultLayout(userId))

  const loadLayout = useCallback(async () => {
    const saved = await window.electronAPI.layoutLoad(userId)
    const valid = validSavedLayout(saved)
    if (valid) {
      setLayout(valid)
    } else if (saved) {
      // An old or damaged file: keep the default tabs and overwrite the file with them,
      // so the stale layout does not come back on the next start.
      setLayout(prev => { save(prev); return prev })
    }
  }, [userId])

  // Back to the five standard tabs. Custom tabs and their layouts are lost.
  const resetTabs = useCallback(() => {
    const next = makeDefaultLayout(userId)
    setLayout(next)
    save(next)
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

  return { layout, loadLayout, resetTabs, addTab, removeTab, renameTab, setActiveTab, updateTabDockview }
}
