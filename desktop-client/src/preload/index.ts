import { contextBridge, ipcRenderer } from 'electron'

contextBridge.exposeInMainWorld('electronAPI', {
  getToken: (): Promise<string | null> =>
    ipcRenderer.invoke('token:get'),
  setToken: (token: string): Promise<void> =>
    ipcRenderer.invoke('token:set', token),
  getHost: (): Promise<string> =>
    ipcRenderer.invoke('config:getHost'),
  setHost: (url: string): Promise<void> =>
    ipcRenderer.invoke('config:setHost', url),
  getMachineStatus: (): Promise<unknown> =>
    ipcRenderer.invoke('machine:status'),
  listFiles: (): Promise<unknown[]> =>
    ipcRenderer.invoke('files:list'),
  layoutLoad: (userId: string): Promise<unknown | null> =>
    ipcRenderer.invoke('layout:load', userId),
  layoutSave: (layout: unknown): Promise<void> =>
    ipcRenderer.invoke('layout:save', layout),
  odooLogin: (payload: { url: string; db?: string; username: string; password: string }): Promise<{ uid: number; name: string; sessionId: string; url: string }> =>
    ipcRenderer.invoke('auth:odooLogin', payload),
  getSession: (): Promise<{ uid: number; name: string; sessionId: string; url: string } | null> =>
    ipcRenderer.invoke('auth:getSession'),
  logout: (): Promise<void> =>
    ipcRenderer.invoke('auth:logout'),
})
