import { app, ipcMain } from 'electron'
import * as nodeFs from 'fs'
import { join } from 'path'

const fs = nodeFs.promises
import { getToken, setToken, getHost, setHost } from './token-store'
import { saveOdooSession, loadOdooSession, clearOdooSession } from './session-store'

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

  ipcMain.handle('layout:load', async (_, userId: string) => {
    const file = join(app.getPath('userData'), 'layouts', `${userId}.json`)
    try {
      const raw = await fs.readFile(file, 'utf-8')
      return JSON.parse(raw as unknown as string)
    } catch {
      return null
    }
  })

  ipcMain.handle('layout:save', async (_, layout: unknown) => {
    const dir = join(app.getPath('userData'), 'layouts')
    await fs.mkdir(dir, { recursive: true })
    const l = layout as { userId: string }
    await fs.writeFile(join(dir, `${l.userId}.json`), JSON.stringify(layout, null, 2), 'utf-8')
  })

  ipcMain.handle('auth:odooLogin', async (_, payload: { url: string; username: string; password: string }) => {
    const res = await fetch(`${payload.url}/web/session/authenticate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        jsonrpc: '2.0', method: 'call', id: 1,
        params: { db: false, login: payload.username, password: payload.password }
      })
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const body = await res.json() as { result?: { uid: number | false; name: string; session_id: string } }
    if (!body.result || body.result.uid === false) throw new Error('Login failed — check username and password')
    const session = {
      uid: body.result.uid as number,
      name: body.result.name,
      sessionId: body.result.session_id,
      url: payload.url,
    }
    await saveOdooSession(session)
    return session
  })

  ipcMain.handle('auth:getSession', () => loadOdooSession())

  ipcMain.handle('auth:logout', () => clearOdooSession())
}
