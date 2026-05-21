import { ipcMain } from 'electron'
import { getToken, setToken, getHost, setHost } from './token-store'

export function registerIpcHandlers(): void {
  ipcMain.handle('token:get', () => getToken())
  ipcMain.handle('token:set', (_, token: string) => setToken(token))
  ipcMain.handle('config:getHost', () => getHost())
  ipcMain.handle('config:setHost', (_, url: string) => setHost(url))

  ipcMain.handle('machine:status', async () => {
    const [host, token] = await Promise.all([getHost(), getToken()])
    if (!token) throw new Error('No token configured')
    const res = await fetch(`${host}/machine/status`, {
      headers: { Authorization: `Bearer ${token}` }
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    return res.json()
  })

  ipcMain.handle('files:list', async () => {
    const [host, token] = await Promise.all([getHost(), getToken()])
    if (!token) throw new Error('No token configured')
    const res = await fetch(`${host}/workspace/files`, {
      headers: { Authorization: `Bearer ${token}` }
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json() as { files: unknown[] }
    return data.files
  })
}
