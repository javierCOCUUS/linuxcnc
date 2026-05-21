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
})
