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

  useEffect(() => {
    loadLayout()
  }, [loadLayout])

  useEffect(() => {
    return () => { disposeRef.current?.() }
  }, [])

  const activeTab = layout.tabs.find((t) => t.id === layout.activeTabId) ?? layout.tabs[0]
  if (!activeTab) return null

  function handleDockviewReady(event: { api: DockviewApi }): void {
    dockviewApiRef.current = event.api
    if (activeTab.dockviewState) {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      event.api.fromJSON(activeTab.dockviewState as any)
    } else {
      event.api.addPanel({ id: 'machine-status-default', component: 'machine-status', title: 'Machine Status' })
      event.api.addPanel({ id: 'position-xyz-default', component: 'position-xyz', title: 'Position XYZ', position: { direction: 'right', referencePanel: 'machine-status-default' } })
    }
    disposeRef.current?.()
    const { dispose } = event.api.onDidLayoutChange(() => {
      updateTabDockview(activeTab.id, event.api.toJSON() as object)
    })
    disposeRef.current = dispose
  }

  function handleAddPanel(panel: { type: string; title: string }): void {
    const api = dockviewApiRef.current
    if (!api) return
    const component = panel.type === 'machine-status' ? 'machine-status'
      : panel.type === 'position-xyz' ? 'position-xyz'
      : panel.type === 'diagnostic' ? 'diagnostic'
      : panel.type === 'alarms' ? 'alarms'
      : panel.type === 'config' ? 'config'
      : 'placeholder'
    api.addPanel({
      id: `${panel.type}-${Date.now()}`,
      component,
      title: panel.title,
      params: { type: panel.type },
      position: { direction: 'right' },
    })
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
