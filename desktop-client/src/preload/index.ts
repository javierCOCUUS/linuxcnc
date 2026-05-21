import { contextBridge } from 'electron'

// Populated in Task 4 — ipc-handlers + preload bridge
contextBridge.exposeInMainWorld('electronAPI', {})
