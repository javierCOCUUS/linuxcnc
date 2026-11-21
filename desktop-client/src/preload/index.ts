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
  getMachineHealth: (): Promise<unknown> =>
    ipcRenderer.invoke('machine:health'),
  jog: (params: { axis: string; distance: number; speed: number }): Promise<unknown> =>
    ipcRenderer.invoke('machine:jog', params),
  setSpindle: (params: { state: 'on' | 'reverse' | 'off'; rpm: number }): Promise<unknown> =>
    ipcRenderer.invoke('machine:spindle', params),
  sendGcode: (line: string): Promise<unknown> =>
    ipcRenderer.invoke('machine:gcode', line),
  getRole: (): Promise<{ role: 'machine' | 'operator'; operatorEnabled: boolean }> =>
    ipcRenderer.invoke('machine:role'),
  setOverride: (params: { kind: 'feed' | 'spindle'; percent: number }): Promise<unknown> =>
    ipcRenderer.invoke('machine:override', params),
  programCommand: (params: { action: string; filename?: string; line?: number }): Promise<unknown> =>
    ipcRenderer.invoke('machine:program', params),
  positionCommand: (params: { action: 'park' | 'goto-zero' | 'zero'; axis?: string }): Promise<unknown> =>
    ipcRenderer.invoke('machine:position', params),
  setEstop: (active: boolean): Promise<unknown> =>
    ipcRenderer.invoke('machine:estop', active),
  setPower: (on: boolean): Promise<unknown> =>
    ipcRenderer.invoke('machine:power', on),
  homeAll: (): Promise<unknown> =>
    ipcRenderer.invoke('machine:home'),
  getHalInputs: (): Promise<unknown[]> =>
    ipcRenderer.invoke('hal:inputs'),
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
