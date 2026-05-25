import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('keytar', () => ({
  default: {
    getPassword: vi.fn(),
    setPassword: vi.fn(),
    deletePassword: vi.fn(),
  }
}))

import keytar from 'keytar'
import { getToken, setToken, deleteToken, getHost, setHost } from '../../src/main/token-store'

beforeEach(() => vi.clearAllMocks())

describe('getToken', () => {
  it('returns stored token from Credential Manager', async () => {
    vi.mocked(keytar.getPassword).mockResolvedValue('tok-abc')
    expect(await getToken()).toBe('tok-abc')
    expect(keytar.getPassword).toHaveBeenCalledWith('mcp-cnc', 'api-token')
  })

  it('returns null when no token stored', async () => {
    vi.mocked(keytar.getPassword).mockResolvedValue(null)
    expect(await getToken()).toBeNull()
  })
})

describe('setToken', () => {
  it('stores token in Credential Manager', async () => {
    vi.mocked(keytar.setPassword).mockResolvedValue(undefined)
    await setToken('tok-xyz')
    expect(keytar.setPassword).toHaveBeenCalledWith('mcp-cnc', 'api-token', 'tok-xyz')
  })
})

describe('deleteToken', () => {
  it('deletes token from Credential Manager', async () => {
    vi.mocked(keytar.deletePassword).mockResolvedValue(true)
    await deleteToken()
    expect(keytar.deletePassword).toHaveBeenCalledWith('mcp-cnc', 'api-token')
  })
})

describe('getHost', () => {
  it('returns stored host URL', async () => {
    vi.mocked(keytar.getPassword).mockResolvedValue('http://192.168.1.10:8006')
    expect(await getHost()).toBe('http://192.168.1.10:8006')
    expect(keytar.getPassword).toHaveBeenCalledWith('mcp-cnc', 'host-url')
  })

  it('returns placeholder default when no host stored', async () => {
    vi.mocked(keytar.getPassword).mockResolvedValue(null)
    expect(await getHost()).toBe('http://100.125.134.3:8006')
  })
})

describe('setHost', () => {
  it('stores host URL in Credential Manager', async () => {
    vi.mocked(keytar.setPassword).mockResolvedValue(undefined)
    await setHost('http://10.0.0.5:8006')
    expect(keytar.setPassword).toHaveBeenCalledWith('mcp-cnc', 'host-url', 'http://10.0.0.5:8006')
  })
})
