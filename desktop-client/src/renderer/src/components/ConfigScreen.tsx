import { useState, useEffect } from 'react'

export function ConfigScreen(): JSX.Element {
  const [host, setHost] = useState('')
  const [token, setToken] = useState('')
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    Promise.all([
      window.electronAPI.getHost(),
      window.electronAPI.getToken(),
    ]).then(([h, t]) => {
      setHost(h)
      setToken(t ?? '')
    })
  }, [])

  async function handleSave(): Promise<void> {
    await Promise.all([
      window.electronAPI.setHost(host),
      window.electronAPI.setToken(token),
    ])
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  return (
    <div className="config-screen">
      <h2>Configuration</h2>
      <div className="config-field">
        <label>Backend URL</label>
        <input
          value={host}
          onChange={e => setHost(e.target.value)}
          placeholder="http://192.168.1.x:8006"
        />
      </div>
      <div className="config-field">
        <label>API Token</label>
        <input
          type="password"
          value={token}
          onChange={e => setToken(e.target.value)}
          placeholder="PLUGIN_API_TOKEN value from .env"
        />
      </div>
      <button onClick={handleSave}>Save</button>
      {saved && <span className="saved-msg">Saved</span>}
    </div>
  )
}
