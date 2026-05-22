import { useState, FormEvent } from 'react'
import type { OdooSession } from '../types/electron-api'

interface LoginScreenProps {
  onLoginSuccess: (session: OdooSession) => void
}

export function LoginScreen({ onLoginSuccess }: LoginScreenProps): JSX.Element {
  const [url, setUrl] = useState('https://tovarna.es')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: FormEvent): Promise<void> {
    e.preventDefault()
    setLoading(true)
    setError(null)
    try {
      const session = await window.electronAPI.odooLogin({ url, username, password })
      onLoginSuccess(session)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="login-screen">
      <div className="login-card">
        <h1 className="login-title">MCP-CNC Desktop</h1>
        <form className="login-form" onSubmit={handleSubmit}>
          <label htmlFor="login-url">Odoo URL</label>
          <input
            id="login-url"
            type="text"
            value={url}
            onChange={e => setUrl(e.target.value)}
            autoComplete="url"
          />
          <label htmlFor="login-username">Username</label>
          <input
            id="login-username"
            type="text"
            value={username}
            onChange={e => setUsername(e.target.value)}
            autoComplete="username"
          />
          <label htmlFor="login-password">Password</label>
          <input
            id="login-password"
            type="password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            autoComplete="current-password"
          />
          {error && <p className="login-error">{error}</p>}
          <button type="submit" disabled={loading}>
            {loading ? 'Logging in…' : 'Login'}
          </button>
        </form>
      </div>
    </div>
  )
}
