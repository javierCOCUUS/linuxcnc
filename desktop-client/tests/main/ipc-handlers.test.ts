import { describe, it, expect, vi, beforeAll } from 'vitest'

vi.mock('electron', () => ({
  ipcMain: { handle: vi.fn() },
  app: { getPath: vi.fn(() => '/tmp/test-userdata') }
}))

vi.mock('keytar', () => ({
  default: {
    getPassword: vi.fn(),
    setPassword: vi.fn(),
    deletePassword: vi.fn(),
  }
}))

vi.mock('../../src/main/token-store', () => ({
  getToken: vi.fn(),
  setToken: vi.fn(),
  getHost: vi.fn(),
  setHost: vi.fn(),
}))

vi.mock('../../src/main/session-store', () => ({
  saveOdooSession: vi.fn(),
  loadOdooSession: vi.fn(),
  clearOdooSession: vi.fn(),
}))

vi.mock('fs', () => ({
  promises: {
    readFile: vi.fn(),
    writeFile: vi.fn(),
    mkdir: vi.fn().mockResolvedValue(undefined),
  }
}))

import { ipcMain } from 'electron'
import * as store from '../../src/main/token-store'
import * as sessionStore from '../../src/main/session-store'
import { promises as fsMock } from 'fs'
import { registerIpcHandlers } from '../../src/main/ipc-handlers'

function getHandler(channel: string): (event: null, ...args: unknown[]) => Promise<unknown> {
  const call = vi.mocked(ipcMain.handle).mock.calls.find(([ch]) => ch === channel)
  if (!call) throw new Error(`No handler registered for channel: ${channel}`)
  return call[1] as ReturnType<typeof getHandler>
}

beforeAll(() => {
  registerIpcHandlers()
})

describe('machine:status', () => {
  it('fetches /machine/status with Bearer token', async () => {
    vi.mocked(store.getHost).mockResolvedValue('http://nas:8006')
    vi.mocked(store.getToken).mockResolvedValue('test-token')
    const mockStatus = { state: 'IDLE', position: { x: 0, y: 0, z: 0 } }
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockStatus)
    }))
    const result = await getHandler('machine:status')(null)
    expect(result).toEqual(mockStatus)
    expect(fetch).toHaveBeenCalledWith('http://nas:8006/machine/status', expect.objectContaining({
      headers: { Authorization: 'Bearer test-token' },
    }))
    vi.unstubAllGlobals()
  })

  it('throws when token is null', async () => {
    vi.mocked(store.getHost).mockResolvedValue('http://nas:8006')
    vi.mocked(store.getToken).mockResolvedValue(null)
    await expect(getHandler('machine:status')(null)).rejects.toThrow('No token configured')
  })

  it('throws when HTTP response is not ok', async () => {
    vi.mocked(store.getHost).mockResolvedValue('http://nas:8006')
    vi.mocked(store.getToken).mockResolvedValue('tok')
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 401 }))
    await expect(getHandler('machine:status')(null)).rejects.toThrow('HTTP 401')
    vi.unstubAllGlobals()
  })
})

describe('machine:status polling stability', () => {
  it('fires only one fetch when called concurrently (single-flight)', async () => {
    vi.mocked(store.getHost).mockResolvedValue('http://nas:8006')
    vi.mocked(store.getToken).mockResolvedValue('tok')
    const mockData = { state: 'IDLE' }
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockData)
    }))
    const handler = getHandler('machine:status')
    const p1 = handler(null)
    const p2 = handler(null)
    const [r1, r2] = await Promise.all([p1, p2])
    expect(fetch).toHaveBeenCalledTimes(1)
    expect(r1).toEqual(mockData)
    expect(r2).toEqual(mockData)
    vi.unstubAllGlobals()
  })

  it('logs duration to console.error when fetch times out', async () => {
    vi.mocked(store.getHost).mockResolvedValue('http://nas:8006')
    vi.mocked(store.getToken).mockResolvedValue('tok')
    const timeoutErr = Object.assign(new Error('The operation was aborted due to timeout'), { name: 'TimeoutError' })
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(timeoutErr))
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {})
    await expect(getHandler('machine:status')(null)).rejects.toThrow()
    expect(spy).toHaveBeenCalledWith(expect.stringMatching(/\[machine:status\].*ms/))
    spy.mockRestore()
    vi.unstubAllGlobals()
  })
})

describe('files:list', () => {
  it('fetches /workspace/files and returns files array', async () => {
    vi.mocked(store.getHost).mockResolvedValue('http://nas:8006')
    vi.mocked(store.getToken).mockResolvedValue('tok')
    const mockData = { files: [{ name: 'a.dxf', size: 100, modified: 1716000000 }] }
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockData)
    }))
    const result = await getHandler('files:list')(null)
    expect(result).toEqual(mockData.files)
    vi.unstubAllGlobals()
  })

  it('throws when token is null', async () => {
    vi.mocked(store.getHost).mockResolvedValue('http://nas:8006')
    vi.mocked(store.getToken).mockResolvedValue(null)
    await expect(getHandler('files:list')(null)).rejects.toThrow('No token configured')
  })
})

describe('auth:odooLogin', () => {
  it('returns session data on successful login', async () => {
    vi.mocked(sessionStore.saveOdooSession).mockResolvedValue(undefined)
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({
        result: { uid: 42, name: 'Javier', session_id: 'abc123' }
      })
    }))
    const result = await getHandler('auth:odooLogin')(null, {
      url: 'https://tovarna.es',
      username: 'javier@zaratiegui.com',
      password: 'pass'
    })
    expect(result).toEqual({ uid: 42, name: 'Javier', sessionId: 'abc123', url: 'https://tovarna.es' })
    vi.unstubAllGlobals()
  })

  it('throws when Odoo returns uid: false (wrong credentials)', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ result: { uid: false } })
    }))
    await expect(getHandler('auth:odooLogin')(null, {
      url: 'https://tovarna.es', username: 'bad@user.com', password: 'wrong'
    })).rejects.toThrow('Login failed')
    vi.unstubAllGlobals()
  })

  it('throws when HTTP response is not ok', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 503 }))
    await expect(getHandler('auth:odooLogin')(null, {
      url: 'https://tovarna.es', username: 'u', password: 'p'
    })).rejects.toThrow('HTTP 503')
    vi.unstubAllGlobals()
  })
})

describe('auth:getSession', () => {
  it('returns null when no session saved', async () => {
    vi.mocked(sessionStore.loadOdooSession).mockResolvedValue(null)
    const result = await getHandler('auth:getSession')(null)
    expect(result).toBeNull()
  })

  it('returns the saved session', async () => {
    const saved = { uid: 1, name: 'J', sessionId: 'sid', url: 'https://tovarna.es' }
    vi.mocked(sessionStore.loadOdooSession).mockResolvedValue(saved)
    const result = await getHandler('auth:getSession')(null)
    expect(result).toEqual(saved)
  })
})

describe('layout:load', () => {
  it('returns null when no layout file exists', async () => {
    vi.mocked(fsMock.readFile).mockRejectedValue(Object.assign(new Error('ENOENT'), { code: 'ENOENT' }))
    const result = await getHandler('layout:load')(null, 'user-42')
    expect(result).toBeNull()
  })

  it('returns parsed JSON when layout file exists', async () => {
    const saved = { version: 1, userId: 'user-42', tabs: [], activeTabId: '' }
    vi.mocked(fsMock.readFile).mockResolvedValue(JSON.stringify(saved) as unknown as Buffer)
    const result = await getHandler('layout:load')(null, 'user-42')
    expect(result).toEqual(saved)
  })
})

describe('layout:save', () => {
  it('writes the layout JSON to the user data directory', async () => {
    vi.mocked(fsMock.mkdir).mockResolvedValue(undefined)
    vi.mocked(fsMock.writeFile).mockResolvedValue(undefined)
    const layout = { version: 1, userId: 'user-42', tabs: [], activeTabId: '' }
    await getHandler('layout:save')(null, layout)
    expect(fsMock.writeFile).toHaveBeenCalledWith(
      expect.stringContaining('user-42.json'),
      JSON.stringify(layout, null, 2),
      'utf-8'
    )
  })
})
