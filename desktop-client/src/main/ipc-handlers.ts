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
          signal: AbortSignal.timeout(12000),
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

  ipcMain.handle('machine:health', async () => {
    const [host, token] = await Promise.all([getHost(), getToken()])
    if (!token) throw new Error('No token configured')
    const res = await fetch(`${host}/machine/health`, {
      headers: { Authorization: `Bearer ${token}` },
      signal: AbortSignal.timeout(15000),
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    return res.json()
  })

  // POST to the backend with the stored token. Errors carry the backend's `detail`
  // text so the panel can show why a motion command was refused.
  async function postMachine(path: string, body: unknown): Promise<unknown> {
    const [host, token] = await Promise.all([getHost(), getToken()])
    if (!token) throw new Error('No token configured')
    const res = await fetch(`${host}${path}`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(15000),
    })
    if (!res.ok) {
      let detail = `HTTP ${res.status}`
      try {
        const err = await res.json() as { detail?: unknown }
        if (typeof err.detail === 'string' && err.detail) detail = err.detail
      } catch {
        // body was not JSON: keep the HTTP status
      }
      throw new Error(detail)
    }
    return res.json()
  }

  const JOG_AXES = ['X', 'Y', 'Z', 'A', 'B', 'C']
  const MAX_JOG_DISTANCE_MM = 100
  const MAX_JOG_SPEED = 5000

  // Limits are enforced here as well as in the panel, so a bad renderer call
  // cannot ask for a huge or malformed move.
  ipcMain.handle('machine:jog', (_, p: { axis: string; distance: number; speed: number }) => {
    const axis = String(p?.axis ?? '').toUpperCase()
    if (!JOG_AXES.includes(axis)) throw new Error(`Invalid axis: ${p?.axis}`)
    if (!Number.isFinite(p.distance) || p.distance === 0 || Math.abs(p.distance) > MAX_JOG_DISTANCE_MM) {
      throw new Error(`Invalid jog distance: ${p.distance}`)
    }
    if (!Number.isFinite(p.speed) || p.speed <= 0 || p.speed > MAX_JOG_SPEED) {
      throw new Error(`Invalid jog speed: ${p.speed}`)
    }
    return postMachine('/machine/jog', { axis, distance: p.distance, speed: p.speed, confirm: true })
  })

  const SPINDLE_STATES = ['on', 'reverse', 'off']
  const MAX_SPINDLE_RPM = 30000
  const MAX_GCODE_LINE = 200

  ipcMain.handle('machine:spindle', (_, p: { state: string; rpm: number }) => {
    if (!SPINDLE_STATES.includes(p?.state)) throw new Error(`Invalid spindle state: ${p?.state}`)
    const rpm = p.state === 'off' ? 0 : p.rpm
    if (!Number.isInteger(rpm) || rpm < 0 || rpm > MAX_SPINDLE_RPM) {
      throw new Error(`Invalid spindle speed: ${p.rpm}`)
    }
    if (p.state !== 'off' && rpm === 0) throw new Error('Spindle speed must be above 0')
    return postMachine('/machine/spindle', { spindle_speed: rpm, state: p.state, confirm: true })
  })

  // One MDI line at a time; a macro is run by the panel line by line so it can stop at the first error.
  ipcMain.handle('machine:gcode', (_, line: string) => {
    const text = String(line ?? '').trim()
    if (!text || text.length > MAX_GCODE_LINE || /[^\x20-\x7e]/.test(text)) {
      throw new Error('Invalid G-code line')
    }
    return postMachine('/machine/gcode', { gcode: text, confirm: true })
  })

  // Which role the stored token has. An older backend without /whoami has a single token that
  // can do everything, so a 404 means "machine".
  ipcMain.handle('machine:role', async () => {
    const [host, token] = await Promise.all([getHost(), getToken()])
    if (!token) throw new Error('No token configured')
    const res = await fetch(`${host}/whoami`, {
      headers: { Authorization: `Bearer ${token}` },
      signal: AbortSignal.timeout(8000),
    })
    if (res.status === 404) return { role: 'machine', operatorEnabled: false }
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const body = await res.json() as { role?: string; operator_enabled?: boolean }
    return { role: body.role === 'operator' ? 'operator' : 'machine', operatorEnabled: Boolean(body.operator_enabled) }
  })

  const OVERRIDE_KINDS = ['feed', 'spindle']
  const MAX_OVERRIDE = 200
  ipcMain.handle('machine:override', (_, p: { kind: string; percent: number }) => {
    if (!OVERRIDE_KINDS.includes(p?.kind)) throw new Error(`Invalid override: ${p?.kind}`)
    if (!Number.isInteger(p.percent) || p.percent < 0 || p.percent > MAX_OVERRIDE) {
      throw new Error(`Invalid override percent: ${p.percent}`)
    }
    return postMachine(`/machine/override/${p.kind}`, { percent: p.percent })
  })

  const PROGRAM_ACTIONS = ['open', 'run', 'pause', 'resume', 'step', 'stop', 'rewind']
  // A bare file name inside the machine's program folder: no path, no spaces at the ends.
  const PROGRAM_FILE = /^[A-Za-z0-9._ -]{1,100}$/
  ipcMain.handle('machine:program', (_, p: { action: string; filename?: string; line?: number }) => {
    if (!PROGRAM_ACTIONS.includes(p?.action)) throw new Error(`Invalid program action: ${p?.action}`)
    if (p.action === 'open') {
      const name = String(p.filename ?? '')
      if (!PROGRAM_FILE.test(name) || name !== name.trim() || name.includes('..')) {
        throw new Error('Invalid file name')
      }
      return postMachine('/machine/program/open', { filename: name, confirm: true })
    }
    if (p.action === 'run') {
      const line = p.line ?? 0
      if (!Number.isInteger(line) || line < 0) throw new Error(`Invalid start line: ${p.line}`)
      return postMachine('/machine/program/run', { line, confirm: true })
    }
    return postMachine(`/machine/program/${p.action}`, { confirm: true })
  })

  const POSITION_ACTIONS = ['park', 'goto-zero', 'zero']
  const ZERO_AXES = ['X', 'Y', 'Z']
  ipcMain.handle('machine:position', (_, p: { action: string; axis?: string }) => {
    if (!POSITION_ACTIONS.includes(p?.action)) throw new Error(`Invalid position action: ${p?.action}`)
    if (p.action === 'zero') {
      const axis = String(p.axis ?? '').toUpperCase()
      if (!ZERO_AXES.includes(axis)) throw new Error(`Invalid axis: ${p.axis}`)
      return postMachine('/machine/zero', { axis, confirm: true })
    }
    return postMachine(`/machine/${p.action}`, { confirm: true })
  })

  ipcMain.handle('machine:estop', (_, active: boolean) =>
    postMachine('/machine/estop', { active: Boolean(active), confirm: true }))

  ipcMain.handle('machine:power', (_, on: boolean) =>
    postMachine('/machine/power', { on: Boolean(on), confirm: true }))

  ipcMain.handle('machine:home', () =>
    postMachine('/machine/home', { confirm: true }))

  let halInputsPromise: Promise<unknown> | null = null

  // Read-only: asks the backend for the 7i95 input pins and their wired signals.
  ipcMain.handle('hal:inputs', () => {
    if (halInputsPromise) return halInputsPromise
    halInputsPromise = (async () => {
      try {
        const [host, token] = await Promise.all([getHost(), getToken()])
        if (!token) throw new Error('No token configured')
        const filter = encodeURIComponent('inmux.00.input-')
        const res = await fetch(`${host}/hal/pins?filter=${filter}`, {
          headers: { Authorization: `Bearer ${token}` },
          signal: AbortSignal.timeout(8000),
        })
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const body = await res.json() as { pins?: unknown[] }
        return body.pins ?? []
      } finally {
        halInputsPromise = null
      }
    })()
    return halInputsPromise
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
