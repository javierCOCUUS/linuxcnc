import { describe, it, expect, vi, beforeAll } from 'vitest'

vi.mock('electron', () => ({
  ipcMain: { handle: vi.fn() }
}))
vi.mock('../../src/main/token-store', () => ({
  getToken: vi.fn(),
  setToken: vi.fn(),
  getHost: vi.fn(),
  setHost: vi.fn(),
}))

import { ipcMain } from 'electron'
import * as store from '../../src/main/token-store'
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
    expect(fetch).toHaveBeenCalledWith('http://nas:8006/machine/status', {
      headers: { Authorization: 'Bearer test-token' }
    })
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
