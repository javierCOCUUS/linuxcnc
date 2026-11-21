import { useEffect, useRef } from 'react'
import { DockviewReact } from 'dockview'
import 'dockview/dist/styles/dockview.css'
import type { DockviewApi, IDockviewPanelProps } from 'dockview'
import { TabBar } from './TabBar'
import { PanelPicker } from './PanelPicker'
import { GlobalStatus } from './GlobalStatus'
import { PlaceholderPanel } from './panels/PlaceholderPanel'
import { MachineStatusPanel } from './panels/MachineStatusPanel'
import { PositionXYZPanel } from './panels/PositionXYZPanel'
import { DiagnosticPanel } from './panels/DiagnosticPanel'
import { AlarmsPanel } from './panels/AlarmsPanel'
import { FilePanel } from './FilePanel'
import { ServicesPanel } from './panels/ServicesPanel'
import { IoInputsPanel } from './panels/IoInputsPanel'
import { JogControlPanel } from './panels/JogControlPanel'
import { ConfigScreen } from './ConfigScreen'
import { MachineDataProvider } from '../context/MachineDataContext'
import { useLayoutStore } from '../store/layout'
import { getTemplate } from '../lib/templates'
import { applyTemplate, openPanel } from '../lib/workspace'

type PanelProps = IDockviewPanelProps<{ type: string }>

// One entry per panel type. Types still without a real panel show the placeholder.
const components = {
  'machine-status': (_props: PanelProps) => <MachineStatusPanel />,
  'position-xyz':   (_props: PanelProps) => <PositionXYZPanel />,
  'jog-control':    (_props: PanelProps) => <JogControlPanel />,
  'io-inputs':      (_props: PanelProps) => <IoInputsPanel />,
  'diagnostic':     (_props: PanelProps) => <DiagnosticPanel />,
  'alarms':         (_props: PanelProps) => <AlarmsPanel />,
  'file-manager':   (_props: PanelProps) => <FilePanel />,
  'services':       (_props: PanelProps) => <ServicesPanel />,
  'config':         (_props: PanelProps) => <ConfigScreen />,
  'visualizer':     (props: PanelProps) => <PlaceholderPanel type={props.params?.type ?? 'visualizer'} />,
  'dxf-cam':        (props: PanelProps) => <PlaceholderPanel type={props.params?.type ?? 'dxf-cam'} />,
  'gcode-editor':   (props: PanelProps) => <PlaceholderPanel type={props.params?.type ?? 'gcode-editor'} />,
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

  function buildFromTemplate(api: DockviewApi): void {
    api.clear()
    applyTemplate(api, getTemplate(activeTab.template))
  }

  function handleDockviewReady(event: { api: DockviewApi }): void {
    const api = event.api
    dockviewApiRef.current = api
    if (activeTab.dockviewState) {
      // A saved layout that cannot be restored must never leave the tab blank or broken.
      try {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        api.fromJSON(activeTab.dockviewState as any)
        if (api.panels && api.panels.length === 0) buildFromTemplate(api)
      } catch {
        buildFromTemplate(api)
      }
    } else {
      applyTemplate(api, getTemplate(activeTab.template))
    }
    disposeRef.current?.()
    const { dispose } = api.onDidLayoutChange(() => {
      updateTabDockview(activeTab.id, api.toJSON() as object)
    })
    disposeRef.current = dispose
  }

  function handleResetLayout(): void {
    const api = dockviewApiRef.current
    if (api) buildFromTemplate(api)
  }

  function handleAddPanel(panel: { type: string; title: string }): void {
    const api = dockviewApiRef.current
    if (api) openPanel(api, panel.type)
  }

  async function handleLogout(): Promise<void> {
    await window.electronAPI.logout()
    onLogout()
  }

  return (
    <MachineDataProvider>
      <div className="app-shell">
        <header className="shell-header">
          <span className="shell-title">MCP-CNC</span>
          <GlobalStatus />
          <span className="shell-user">{userName}</span>
          <button className="shell-reset" onClick={handleResetLayout} aria-label="Reset layout" title="Restablecer esta pestaña">
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
            onTabAdd={() => addTab()}
            onTabRemove={removeTab}
            onTabRename={renameTab}
          />
          <PanelPicker onAddPanel={handleAddPanel} />
        </div>
        <div className="shell-workspace">
          <DockviewReact
            key={activeTab.id}
            className="dockview-theme-dark"
            components={components}
            onReady={handleDockviewReady}
          />
        </div>
      </div>
    </MachineDataProvider>
  )
}
