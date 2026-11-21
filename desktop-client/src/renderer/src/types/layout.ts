export type TemplateId =
  | 'operacion'
  | 'puesta-en-marcha'
  | 'diagnostico'
  | 'produccion'
  | 'cam'

export interface TabLayout {
  id: string
  label: string
  /** Layout the tab starts from, and the one "Reset layout" restores. */
  template: TemplateId
  dockviewState: object | null
}

export interface WorkspaceLayout {
  version: 2
  userId: string
  tabs: TabLayout[]
  activeTabId: string
}
