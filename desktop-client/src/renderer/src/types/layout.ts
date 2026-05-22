export interface TabLayout {
  id: string
  label: string
  dockviewState: object | null
}

export interface WorkspaceLayout {
  version: 1
  userId: string
  tabs: TabLayout[]
  activeTabId: string
}
