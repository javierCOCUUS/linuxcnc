import keytar from 'keytar'

const SERVICE = 'mcp-cnc'
const TOKEN_ACCOUNT = 'api-token'
const HOST_ACCOUNT = 'host-url'

export async function getToken(): Promise<string | null> {
  return keytar.getPassword(SERVICE, TOKEN_ACCOUNT)
}

export async function setToken(token: string): Promise<void> {
  await keytar.setPassword(SERVICE, TOKEN_ACCOUNT, token)
}

export async function deleteToken(): Promise<void> {
  await keytar.deletePassword(SERVICE, TOKEN_ACCOUNT)
}

export async function getHost(): Promise<string> {
  const stored = await keytar.getPassword(SERVICE, HOST_ACCOUNT)
  return stored ?? 'http://100.125.134.3:8006'
}

export async function setHost(url: string): Promise<void> {
  await keytar.setPassword(SERVICE, HOST_ACCOUNT, url)
}

const BRIDGE_ACCOUNT = 'bridge-url'

export async function getBridgeUrl(): Promise<string> {
  const stored = await keytar.getPassword(SERVICE, BRIDGE_ACCOUNT)
  return stored ?? 'http://100.125.134.3:8000'
}

export async function setBridgeUrl(url: string): Promise<void> {
  await keytar.setPassword(SERVICE, BRIDGE_ACCOUNT, url)
}
