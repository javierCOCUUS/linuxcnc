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

  useEffect(() => {
    window.electronAPI.getHost().then(host => {
      setSrc(buildVisualizerUrl(host))
    })
  }, [])

  if (!src) return <div className="visualizer-panel">Loading...</div>

  return (
    <div className="visualizer-panel">
      {/* webviewTag: true is set in BrowserWindow.webPreferences (src/main/index.ts) */}
      <webview src={src} style={{ width: '100%', height: '100%', border: 'none' }} />
    </div>
  )
}
