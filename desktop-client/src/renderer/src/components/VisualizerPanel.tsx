import { useState, useEffect } from 'react'

function buildVisualizerUrl(orchestratorUrl: string): string {
  try {
    const u = new URL(orchestratorUrl)
    return `${u.protocol}//${u.hostname}:8007/`
  } catch {
    return ''
  }
}

export function VisualizerPanel(): JSX.Element {
  const [src, setSrc] = useState('')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    window.electronAPI.getHost()
      .then(host => {
        if (!cancelled) setSrc(buildVisualizerUrl(host))
      })
      .catch(err => {
        if (!cancelled) setError(String(err))
      })
    return () => { cancelled = true }
  }, [])

  if (error) return <div className="visualizer-panel visualizer-panel--error">⚠ {error}</div>
  if (!src) return <div className="visualizer-panel">Loading...</div>

  return (
    <div className="visualizer-panel">
      {/* webviewTag: true is set in BrowserWindow.webPreferences (src/main/index.ts) */}
      <webview src={src} style={{ width: '100%', height: '100%', border: 'none' }} />
    </div>
  )
}
