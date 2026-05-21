import type { MachineStatus, WorkspaceFile } from './api'

declare global {
  interface Window {
    electronAPI: {
      getToken(): Promise<string | null>
      setToken(token: string): Promise<void>
      getHost(): Promise<string>
      setHost(url: string): Promise<void>
      getMachineStatus(): Promise<MachineStatus>
      listFiles(): Promise<WorkspaceFile[]>
    }
  }
}
