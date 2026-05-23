import { useEffect, useRef } from 'react'
import { DockviewReact } from 'dockview'
import type { DockviewApi, IDockviewPanelProps } from 'dockview'
import { TabBar } from './TabBar'
import { PanelPicker } from './PanelPicker'
import { PlaceholderPanel } from './panels/PlaceholderPanel'
import { MachineStatusPanel } from './panels/MachineStatusPanel'
import { PositionXYZPanel } from './panels/PositionXYZPanel'
import { DiagnosticPanel } from './panels/DiagnosticPanel'
import { AlarmsPanel } from './panels/AlarmsPanel'
import { FileManagerPanel } from './panels/FileManagerPanel'
import { ConfigScreen } from './ConfigScreen'
import { MachineDataProvider } from '../context/MachineDataContext'
import { useLayoutStore } from '../store/layout'

// Import dockview CSS (skipped in test/jsdom environments via vitest css:false)
try {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  require('dockview/dist/styles/dockview.css')
} catch {
  // CSS import not available in test environments
}

const components = {
  placeholder: (props: IDockviewPanelProps<{ type: string }>) => (
    <PlaceholderPanel type={props.params.type} />
  ),
  'machine-status': (_props: IDockviewPanelProps<{ type: string }>) => (
    <MachineStatusPanel />
  ),
  'position-xyz': (_props: IDockviewPanelProps<{ type: string }>) => (
    <PositionXYZPanel />
  ),
  'diagnostic': (_props: IDockviewPanelProps<{ type: string }>) => (
    <DiagnosticPanel />
  ),
  'alarms': (_props: IDockviewPanelProps<{ type: string }>) => (
    <AlarmsPanel />
  ),
  'file-manager': (_props: IDockviewPanelProps<{ type: string }>) => (
    <FileManagerPanel />
  ),
  'config': (_props: IDockviewPanelProps<{ type: string }>) => (
    <ConfigScreen />
  ),
}

interface AppShellProps {
  userId: string
  userName: string
  onLogout: () => void
}

export function AppShell({ userId, userName, onLogout }: AppShellProps): JSX.Element | null {
  const { layout, loadLayout, addTab, removeTab, renameTab, setActiveTab, updateTabDockview } =
    useLayoutStore(userId)
  const dockviewApiRef = useRef<DockviewApi | null>(null)
  const disposeRef = useRef<(() => void) | null>(null)
  // Tracks the last panel added to each column for 2-column stacking
  const leftAnchorRef = useRef<string | null>(null)
  const rightAnchorRef = useRef<string | null>(null)
  const nextColumnRef = useRef<'left' | 'right'>('left')

  useEffect(() => {
    loadLayout()
  }, [loadLayout])

  useEffect(() => {
    return () => { disposeRef.current?.() }
  }, [])

  const activeTab = layout.tabs.find((t) => t.id === layout.activeTabId) ?? layout.tabs[0]
  if (!activeTab) return null

  function addDefaultPanels(api: DockviewApi): void {
    const p1 = api.addPanel({ id: 'machine-status-default', component: 'machine-status', title: 'Machine Status' })
    const p2 = api.addPanel({ id: 'position-xyz-default', component: 'position-xyz', title: 'Position XYZ', position: { direction: 'right', referencePanel: 'machine-status-default' } })
    leftAnchorRef.current = p1.id
    rightAnchorRef.current = p2.id
    nextColumnRef.current = 'left'
  }

  function handleDockviewReady(event: { api: DockviewApi }): void {
    dockviewApiRef.current = event.api
    if (activeTab.dockviewState) {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      event.api.fromJSON(activeTab.dockviewState as any)
      // Restore anchors from the two known default panels if they still exist
      leftAnchorRef.current = event.api.getPanel('machine-status-default')?.id ?? null
      rightAnchorRef.current = event.api.getPanel('position-xyz-default')?.id ?? null
      nextColumnRef.current = 'left'
    } else {
      addDefaultPanels(event.api)
    }
    disposeRef.current?.()
    const { dispose } = event.api.onDidLayoutChange(() => {
      updateTabDockview(activeTab.id, event.api.toJSON() as object)
    })
    disposeRef.current = dispose
  }

  function handleResetLayout(): void {
    const api = dockviewApiRef.current
    if (!api) return
    api.clear()
    addDefaultPanels(api)
  }

  function handleAddPanel(panel: { type: string; title: string }): void {
    const api = dockviewApiRef.current
    if (!api) return
    const component = panel.type === 'machine-status' ? 'machine-status'
      : panel.type === 'position-xyz' ? 'position-xyz'
      : panel.type === 'diagnostic' ? 'diagnostic'
      : panel.type === 'alarms' ? 'alarms'
      : panel.type === 'file-manager' ? 'file-manager'
      : panel.type === 'config' ? 'config'
      : 'placeholder'

    const id = `${panel.type}-${Date.now()}`
    const leftAnchor = leftAnchorRef.current
    const rightAnchor = rightAnchorRef.current

    // When anchors are known: alternate left/right columns, stacking below the last
    // panel added to that column. When anchors are missing (fresh start with <2 groups):
    // fall back to absolute 'right' to create the second column.
    let position: { direction: 'right' } | { direction: 'below'; referencePanel: string }
    if (!leftAnchor || !rightAnchor || api.groups.length < 2) {
      position = { direction: 'right' }
      if (!rightAnchorRef.current) rightAnchorRef.current = id
    } else {
      const useLeft = nextColumnRef.current === 'left'
      const anchorId = useLeft ? leftAnchor : rightAnchor
      position = { direction: 'below', referencePanel: anchorId }
      if (useLeft) leftAnchorRef.current = id
      else rightAnchorRef.current = id
      nextColumnRef.current = useLeft ? 'right' : 'left'
    }

    api.addPanel({ id, component, title: panel.title, params: { type: panel.type }, position })
  }

  async function handleLogout(): Promise<void> {
    await window.electronAPI.logout()
    onLogout()
  }

  return (
    <div className="app-shell">
      <header className="shell-header">
        <span className="shell-title">MCP-CNC</span>
        <span className="shell-user">{userName}</span>
        <button className="shell-reset" onClick={handleResetLayout} aria-label="Reset layout" title="Reset layout">
          ⊞
        </button>
        <button className="shell-settings" onClick={() => handleAddPanel({ type: 'config', title: 'Settings' })} aria-label="Settings">
          ⚙
        </button>
        <button className="shell-logout" onClick={handleLogout} aria-label="Logout">
          Logout
        </button>
      </header>
      <div className="shell-tab-row">
        <TabBar
          tabs={layout.tabs}
          activeTabId={layout.activeTabId}
          onTabClick={setActiveTab}
          onTabAdd={addTab}
          onTabRemove={removeTab}
          onTabRename={renameTab}
        />
        <PanelPicker onAddPanel={handleAddPanel} />
      </div>
      <div className="shell-workspace">
        <MachineDataProvider>
          <DockviewReact
            key={activeTab.id}
            className="dockview-theme-dark"
            components={components}
            onReady={handleDockviewReady}
          />
        </MachineDataProvider>
      </div>
    </div>
  )
}
