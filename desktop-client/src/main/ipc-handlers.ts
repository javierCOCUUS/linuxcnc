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

  let machineStatusPromise: Promise<unknown> | null = null

  ipcMain.handle('machine:status', () => {
    if (machineStatusPromise) return machineStatusPromise
    const start = Date.now()
    machineStatusPromise = (async () => {
      try {
        const [host, token] = await Promise.all([getHost(), getToken()])
        if (!token) throw new Error('No token configured')
        const res = await fetch(`${host}/machine/status`, {
          headers: { Authorization: `Bearer ${token}` },
          signal: AbortSignal.timeout(5000),
        })
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        return res.json()
      } catch (err) {
        if (err instanceof Error && err.name === 'TimeoutError') {
          console.error(`[machine:status] timeout after ${Date.now() - start}ms`)
        }
        throw err
      } finally {
        machineStatusPromise = null
      }
    })()
    return machineStatusPromise
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

  ipcMain.handle('auth:odooLogin', async (_, payload: { url: string; db?: string; username: string; password: string }) => {
    type OdooAuthBody = {
      result?: { uid: number | false; name: string; session_id: string }
      error?: { message: string; data?: { message?: string } }
    }

    async function attemptLogin(db: string | false): Promise<OdooAuthBody> {
      const res = await fetch(`${payload.url}/web/session/authenticate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          jsonrpc: '2.0', method: 'call', id: 1,
          params: { db, login: payload.username, password: payload.password }
        })
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      return res.json()
    }

    let body = await attemptLogin(payload.db ?? false)

    // uid:false with no explicit db → try to discover the database automatically
    if ((!body.result || body.result.uid === false) && !payload.db) {
      try {
        const dbRes = await fetch(`${payload.url}/web/database/list`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ jsonrpc: '2.0', method: 'call', id: 2, params: {} })
        })
        if (dbRes.ok) {
          const dbBody = await dbRes.json() as { result?: string[] }
          if (dbBody.result?.length === 1) {
            body = await attemptLogin(dbBody.result[0])
          } else if (dbBody.result && dbBody.result.length > 1) {
            throw new Error(`Multiple databases found: ${dbBody.result.join(', ')} — enter the database name in the "Database" field`)
          }
        }
      } catch (e) {
        if (e instanceof Error && e.message.includes('Multiple databases')) throw e
        // Discovery failed or disabled — fall through to original error
      }
    }

    if (body.error) {
      throw new Error(body.error.data?.message ?? body.error.message ?? 'Odoo server error')
    }
    if (!body.result || body.result.uid === false) {
      throw new Error('Login failed — wrong username, password, or database name')
    }

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
