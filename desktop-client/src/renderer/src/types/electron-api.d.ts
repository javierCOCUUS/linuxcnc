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
      setSpindle(params: { state: 'on' | 'reverse' | 'off'; rpm: number }): Promise<unknown>
      sendGcode(line: string): Promise<unknown>
      getRole(): Promise<{ role: 'machine' | 'operator'; operatorEnabled: boolean }>
      setOverride(params: { kind: 'feed' | 'spindle'; percent: number }): Promise<unknown>
      programCommand(params: { action: string; filename?: string; line?: number }): Promise<unknown>
      positionCommand(params: { action: 'park' | 'goto-zero' | 'zero'; axis?: string }): Promise<unknown>
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
