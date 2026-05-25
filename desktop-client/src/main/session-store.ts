import keytar from 'keytar'

const SERVICE = 'mcp-cnc'

export interface OdooSession {
  uid: number
  name: string
  sessionId: string
  url: string
}

export async function saveOdooSession(session: OdooSession): Promise<void> {
  await keytar.setPassword(SERVICE, 'odoo-session', JSON.stringify(session))
}

export async function loadOdooSession(): Promise<OdooSession | null> {
  const raw = await keytar.getPassword(SERVICE, 'odoo-session')
  if (!raw) return null
  try {
    return JSON.parse(raw) as OdooSession
  } catch {
    return null
  }
}

export async function clearOdooSession(): Promise<void> {
  await keytar.deletePassword(SERVICE, 'odoo-session')
}
