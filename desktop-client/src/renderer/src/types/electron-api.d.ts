import type { MachineStatus, MachineHealth, WorkspaceFile, HalPin } from './api'
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
      getMachineHealth(): Promise<MachineHealth>
      jog(params: { axis: string; distance: number; speed: number }): Promise<unknown>
      setEstop(active: boolean): Promise<unknown>
      setPower(on: boolean): Promise<unknown>
      homeAll(): Promise<unknown>
      getHalInputs(): Promise<HalPin[]>
      listFiles(): Promise<WorkspaceFile[]>
      layoutLoad(userId: string): Promise<WorkspaceLayout | null>
      layoutSave(layout: WorkspaceLayout): Promise<void>
      odooLogin(payload: { url: string; db?: string; username: string; password: string }): Promise<OdooSession>
      getSession(): Promise<OdooSession | null>
      logout(): Promise<void>
    }
  }
}
