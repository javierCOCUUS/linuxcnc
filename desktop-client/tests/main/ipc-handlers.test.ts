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

describe('hal:inputs', () => {
  it('fetches /hal/pins filtered to the inmux inputs with Bearer token and returns the pins', async () => {
    vi.mocked(store.getHost).mockResolvedValue('http://nas:8006')
    vi.mocked(store.getToken).mockResolvedValue('test-token')
    const pins = [{ name: 'hm2_7i95.0.inmux.00.input-08', value: 'TRUE' }]
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ status: 'ok', count: 1, pins })
    }))
    const result = await getHandler('hal:inputs')(null)
    expect(result).toEqual(pins)
    expect(fetch).toHaveBeenCalledWith(
      'http://nas:8006/hal/pins?filter=inmux.00.input-',
      expect.objectContaining({ headers: { Authorization: 'Bearer test-token' } })
    )
    vi.unstubAllGlobals()
  })

  it('returns an empty list when the response has no pins', async () => {
    vi.mocked(store.getHost).mockResolvedValue('http://nas:8006')
    vi.mocked(store.getToken).mockResolvedValue('test-token')
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({}) }))
    expect(await getHandler('hal:inputs')(null)).toEqual([])
    vi.unstubAllGlobals()
  })

  it('throws when token is null', async () => {
    vi.mocked(store.getHost).mockResolvedValue('http://nas:8006')
    vi.mocked(store.getToken).mockResolvedValue(null)
    await expect(getHandler('hal:inputs')(null)).rejects.toThrow('No token configured')
  })

  it('throws on a non-ok response', async () => {
    vi.mocked(store.getHost).mockResolvedValue('http://nas:8006')
    vi.mocked(store.getToken).mockResolvedValue('test-token')
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 403 }))
    await expect(getHandler('hal:inputs')(null)).rejects.toThrow('HTTP 403')
    vi.unstubAllGlobals()
  })
})

describe('machine motion handlers', () => {
  function stubOk(): ReturnType<typeof vi.fn> {
    vi.mocked(store.getHost).mockResolvedValue('http://nas:8006')
    vi.mocked(store.getToken).mockResolvedValue('test-token')
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ status: 'ok' }) })
    vi.stubGlobal('fetch', fetchMock)
    return fetchMock
  }

  it('machine:jog POSTs axis, distance, speed and confirm with the Bearer token', async () => {
    const fetchMock = stubOk()
    await getHandler('machine:jog')(null, { axis: 'x', distance: -1, speed: 600 })
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('http://nas:8006/machine/jog')
    expect(init.method).toBe('POST')
    expect(init.headers.Authorization).toBe('Bearer test-token')
    expect(JSON.parse(init.body)).toEqual({ axis: 'X', distance: -1, speed: 600, confirm: true })
    vi.unstubAllGlobals()
  })

  it.each([
    [{ axis: 'Q', distance: 1, speed: 600 }, 'Invalid axis'],
    [{ axis: 'X', distance: 0, speed: 600 }, 'Invalid jog distance'],
    [{ axis: 'X', distance: 101, speed: 600 }, 'Invalid jog distance'],
    [{ axis: 'X', distance: NaN, speed: 600 }, 'Invalid jog distance'],
    [{ axis: 'X', distance: 1, speed: 0 }, 'Invalid jog speed'],
    [{ axis: 'X', distance: 1, speed: 5001 }, 'Invalid jog speed'],
  ])('machine:jog rejects %j without calling the backend', async (params, message) => {
    const fetchMock = stubOk()
    await expect(Promise.resolve().then(() => getHandler('machine:jog')(null, params))).rejects.toThrow(message)
    expect(fetchMock).not.toHaveBeenCalled()
    vi.unstubAllGlobals()
  })

  it('machine:estop, machine:power and machine:home hit their routes with confirm', async () => {
    const fetchMock = stubOk()
    await getHandler('machine:estop')(null, true)
    await getHandler('machine:estop')(null, false)
    await getHandler('machine:power')(null, true)
    await getHandler('machine:home')(null)
    const calls = fetchMock.mock.calls.map(([url, init]) => [url, JSON.parse(init.body)])
    expect(calls).toEqual([
      ['http://nas:8006/machine/estop', { active: true, confirm: true }],
      ['http://nas:8006/machine/estop', { active: false, confirm: true }],
      ['http://nas:8006/machine/power', { on: true, confirm: true }],
      ['http://nas:8006/machine/home', { confirm: true }],
    ])
    vi.unstubAllGlobals()
  })

  it('surfaces the backend detail text on an error response', async () => {
    vi.mocked(store.getHost).mockResolvedValue('http://nas:8006')
    vi.mocked(store.getToken).mockResolvedValue('test-token')
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false, status: 409, json: () => Promise.resolve({ detail: 'LinuxCNC is in E-stop' }),
    }))
    await expect(getHandler('machine:home')(null)).rejects.toThrow('LinuxCNC is in E-stop')
    vi.unstubAllGlobals()
  })

  it('falls back to the HTTP status when the error body is not JSON', async () => {
    vi.mocked(store.getHost).mockResolvedValue('http://nas:8006')
    vi.mocked(store.getToken).mockResolvedValue('test-token')
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false, status: 502, json: () => Promise.reject(new Error('not json')),
    }))
    await expect(getHandler('machine:home')(null)).rejects.toThrow('HTTP 502')
    vi.unstubAllGlobals()
  })

  it('throws when there is no token', async () => {
    vi.mocked(store.getHost).mockResolvedValue('http://nas:8006')
    vi.mocked(store.getToken).mockResolvedValue(null)
    await expect(getHandler('machine:home')(null)).rejects.toThrow('No token configured')
  })
})

describe('spindle and G-code handlers', () => {
  function stubOk(): ReturnType<typeof vi.fn> {
    vi.mocked(store.getHost).mockResolvedValue('http://nas:8006')
    vi.mocked(store.getToken).mockResolvedValue('test-token')
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ status: 'ok' }) })
    vi.stubGlobal('fetch', fetchMock)
    return fetchMock
  }
  const body = (m: ReturnType<typeof vi.fn>) => JSON.parse(m.mock.calls[0][1].body)

  it('machine:spindle POSTs state, rpm and confirm', async () => {
    const fetchMock = stubOk()
    await getHandler('machine:spindle')(null, { state: 'on', rpm: 12000 })
    expect(fetchMock.mock.calls[0][0]).toBe('http://nas:8006/machine/spindle')
    expect(body(fetchMock)).toEqual({ spindle_speed: 12000, state: 'on', confirm: true })
    vi.unstubAllGlobals()
  })

  it('machine:spindle sends rpm 0 for off whatever rpm is given', async () => {
    const fetchMock = stubOk()
    await getHandler('machine:spindle')(null, { state: 'off', rpm: 18000 })
    expect(body(fetchMock)).toEqual({ spindle_speed: 0, state: 'off', confirm: true })
    vi.unstubAllGlobals()
  })

  it.each([
    [{ state: 'spin', rpm: 1000 }, 'Invalid spindle state'],
    [{ state: 'on', rpm: -1 }, 'Invalid spindle speed'],
    [{ state: 'on', rpm: 30001 }, 'Invalid spindle speed'],
    [{ state: 'on', rpm: 1.5 }, 'Invalid spindle speed'],
    [{ state: 'on', rpm: NaN }, 'Invalid spindle speed'],
    [{ state: 'reverse', rpm: 0 }, 'above 0'],
  ])('machine:spindle rejects %j without calling the backend', async (params, message) => {
    const fetchMock = stubOk()
    await expect(Promise.resolve().then(() => getHandler('machine:spindle')(null, params))).rejects.toThrow(message)
    expect(fetchMock).not.toHaveBeenCalled()
    vi.unstubAllGlobals()
  })

  it('machine:gcode POSTs one trimmed line with confirm', async () => {
    const fetchMock = stubOk()
    await getHandler('machine:gcode')(null, '  G0 X10 Y5  ')
    expect(fetchMock.mock.calls[0][0]).toBe('http://nas:8006/machine/gcode')
    expect(body(fetchMock)).toEqual({ gcode: 'G0 X10 Y5', confirm: true })
    vi.unstubAllGlobals()
  })

  it.each([
    ['', 'empty'],
    ['   ', 'blank'],
    ['G0 X1\nG0 X2', 'more than one line'],
    ['G0 X1\u0000', 'control character'],
    ['G0 Xé', 'non-ASCII'],
    ['G'.repeat(201), 'too long'],
  ])('machine:gcode rejects %j (%s) without calling the backend', async (line) => {
    const fetchMock = stubOk()
    await expect(Promise.resolve().then(() => getHandler('machine:gcode')(null, line))).rejects.toThrow('Invalid G-code line')
    expect(fetchMock).not.toHaveBeenCalled()
    vi.unstubAllGlobals()
  })
})

describe('role, override, program and position handlers', () => {
  function stubOk(): ReturnType<typeof vi.fn> {
    vi.mocked(store.getHost).mockResolvedValue('http://nas:8006')
    vi.mocked(store.getToken).mockResolvedValue('test-token')
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200, json: () => Promise.resolve({ status: 'ok' }) })
    vi.stubGlobal('fetch', fetchMock)
    return fetchMock
  }
  const sent = (m: ReturnType<typeof vi.fn>, i = 0) => ({ url: m.mock.calls[i][0], body: JSON.parse(m.mock.calls[i][1].body) })
  const rejects = async (channel: string, params: unknown, message: string, fetchMock: ReturnType<typeof vi.fn>) => {
    await expect(Promise.resolve().then(() => getHandler(channel)(null, params))).rejects.toThrow(message)
    expect(fetchMock).not.toHaveBeenCalled()
  }

  describe('machine:role', () => {
    it('reads the role from /whoami with the Bearer token', async () => {
      vi.mocked(store.getHost).mockResolvedValue('http://nas:8006')
      vi.mocked(store.getToken).mockResolvedValue('test-token')
      const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200, json: () => Promise.resolve({ role: 'operator', operator_enabled: true }) })
      vi.stubGlobal('fetch', fetchMock)
      expect(await getHandler('machine:role')(null)).toEqual({ role: 'operator', operatorEnabled: true })
      expect(fetchMock.mock.calls[0][0]).toBe('http://nas:8006/whoami')
      expect(fetchMock.mock.calls[0][1].headers.Authorization).toBe('Bearer test-token')
      vi.unstubAllGlobals()
    })

    it('treats a backend without /whoami (404) as the machine role', async () => {
      vi.mocked(store.getHost).mockResolvedValue('http://nas:8006')
      vi.mocked(store.getToken).mockResolvedValue('test-token')
      vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 404 }))
      expect(await getHandler('machine:role')(null)).toEqual({ role: 'machine', operatorEnabled: false })
      vi.unstubAllGlobals()
    })

    it('never invents a role from an unexpected value', async () => {
      vi.mocked(store.getHost).mockResolvedValue('http://nas:8006')
      vi.mocked(store.getToken).mockResolvedValue('test-token')
      vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, status: 200, json: () => Promise.resolve({ role: 'admin' }) }))
      expect((await getHandler('machine:role')(null) as { role: string }).role).toBe('machine')
      vi.unstubAllGlobals()
    })

    it('fails on a server error or without a token', async () => {
      vi.mocked(store.getHost).mockResolvedValue('http://nas:8006')
      vi.mocked(store.getToken).mockResolvedValue('test-token')
      vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 401 }))
      await expect(getHandler('machine:role')(null)).rejects.toThrow('HTTP 401')
      vi.mocked(store.getToken).mockResolvedValue(null)
      await expect(getHandler('machine:role')(null)).rejects.toThrow('No token configured')
      vi.unstubAllGlobals()
    })
  })

  describe('machine:override', () => {
    it.each(['feed', 'spindle'])('POSTs the %s override percent', async kind => {
      const m = stubOk()
      await getHandler('machine:override')(null, { kind, percent: 80 })
      expect(sent(m)).toEqual({ url: `http://nas:8006/machine/override/${kind}`, body: { percent: 80 } })
      vi.unstubAllGlobals()
    })

    it.each([
      [{ kind: 'rapid', percent: 80 }, 'Invalid override'],
      [{ kind: 'feed', percent: -1 }, 'Invalid override percent'],
      [{ kind: 'feed', percent: 201 }, 'Invalid override percent'],
      [{ kind: 'feed', percent: 1.5 }, 'Invalid override percent'],
      [{ kind: 'feed', percent: NaN }, 'Invalid override percent'],
      [{ kind: 'feed', percent: '80' }, 'Invalid override percent'],
    ])('rejects %j without calling the backend', async (params, message) => {
      const m = stubOk()
      await rejects('machine:override', params, message, m)
      vi.unstubAllGlobals()
    })
  })

  describe('machine:program', () => {
    it('opens a program by bare file name, with confirm', async () => {
      const m = stubOk()
      await getHandler('machine:program')(null, { action: 'open', filename: 'tapa caja_1.tap' })
      expect(sent(m)).toEqual({ url: 'http://nas:8006/machine/program/open', body: { filename: 'tapa caja_1.tap', confirm: true } })
      vi.unstubAllGlobals()
    })

    it.each([
      ['', 'empty'], ['../etc/passwd', 'parent directory'], ['a/b.tap', 'slash'], ['a\\b.tap', 'backslash'],
      [' a.tap', 'leading space'], ['a.tap ', 'trailing space'], ['a..tap', 'double dot'], ['é.tap', 'non-ASCII'],
      ['a'.repeat(101), 'too long'], ['a;b.tap', 'semicolon'],
    ])('refuses the file name %j (%s)', async name => {
      const m = stubOk()
      await rejects('machine:program', { action: 'open', filename: name }, 'Invalid file name', m)
      vi.unstubAllGlobals()
    })

    it('runs from the beginning by default and from a given line', async () => {
      const m = stubOk()
      await getHandler('machine:program')(null, { action: 'run' })
      await getHandler('machine:program')(null, { action: 'run', line: 120 })
      expect(sent(m, 0).body).toEqual({ line: 0, confirm: true })
      expect(sent(m, 1).body).toEqual({ line: 120, confirm: true })
      expect(sent(m, 0).url).toBe('http://nas:8006/machine/program/run')
      vi.unstubAllGlobals()
    })

    it.each([-1, 1.5, NaN])('refuses the start line %s', async line => {
      const m = stubOk()
      await rejects('machine:program', { action: 'run', line }, 'Invalid start line', m)
      vi.unstubAllGlobals()
    })

    it.each(['pause', 'resume', 'step', 'stop', 'rewind'])('POSTs %s to its own route', async action => {
      const m = stubOk()
      await getHandler('machine:program')(null, { action })
      expect(sent(m).url).toBe(`http://nas:8006/machine/program/${action}`)
      vi.unstubAllGlobals()
    })

    it.each(['delete', 'format', '', undefined])('refuses the unknown action %j', async action => {
      const m = stubOk()
      await rejects('machine:program', { action }, 'Invalid program action', m)
      vi.unstubAllGlobals()
    })
  })

  describe('machine:position', () => {
    it('zeroes X, Y or Z, upper-casing the axis', async () => {
      const m = stubOk()
      await getHandler('machine:position')(null, { action: 'zero', axis: 'y' })
      expect(sent(m)).toEqual({ url: 'http://nas:8006/machine/zero', body: { axis: 'Y', confirm: true } })
      vi.unstubAllGlobals()
    })

    it.each(['A', 'B', 'C', 'Q', '', undefined])('refuses to zero the axis %j', async axis => {
      const m = stubOk()
      await rejects('machine:position', { action: 'zero', axis }, 'Invalid axis', m)
      vi.unstubAllGlobals()
    })

    it.each([['park', '/machine/park'], ['goto-zero', '/machine/goto-zero']])('POSTs %s', async (action, path) => {
      const m = stubOk()
      await getHandler('machine:position')(null, { action })
      expect(sent(m)).toEqual({ url: `http://nas:8006${path}`, body: { confirm: true } })
      vi.unstubAllGlobals()
    })

    it('refuses an unknown action', async () => {
      const m = stubOk()
      await rejects('machine:position', { action: 'teleport' }, 'Invalid position action', m)
      vi.unstubAllGlobals()
    })
  })

  it('surfaces the 403 text of a role refusal', async () => {
    vi.mocked(store.getHost).mockResolvedValue('http://nas:8006')
    vi.mocked(store.getToken).mockResolvedValue('test-token')
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false, status: 403,
      json: () => Promise.resolve({ detail: 'Esta acción solo se acepta desde la pantalla de la máquina' }),
    }))
    await expect(getHandler('machine:program')(null, { action: 'resume' })).rejects.toThrow('pantalla de la máquina')
    vi.unstubAllGlobals()
  })
})
