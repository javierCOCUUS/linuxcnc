import type { MachineStatus, WorkspaceFile } from './api'
import type { WorkspaceLayout } from './layout'

export interface OdooSession {
  uid: number
  name: string
  sessionId: string
  url: string
}

declare global {
  interface Window {
    electronAPI: {
      getToken(): Promise<string | null>
      setToken(token: string): Promise<void>
      getHost(): Promise<string>
      setHost(url: string): Promise<void>
      getMachineStatus(): Promise<MachineStatus>
      listFiles(): Promise<WorkspaceFile[]>
      layoutLoad(userId: string): Promise<WorkspaceLayout | null>
      layoutSave(layout: WorkspaceLayout): Promise<void>
      odooLogin(payload: { url: string; username: string; password: string }): Promise<OdooSession>
      getSession(): Promise<OdooSession | null>
      logout(): Promise<void>
    }
  }
}
