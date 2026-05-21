import { useState, useEffect } from 'react'
import { StatusBar } from './components/StatusBar'
import { VisualizerPanel } from './components/VisualizerPanel'
import { FilePanel } from './components/FilePanel'
import { ConfigScreen } from './components/ConfigScreen'

export function App(): JSX.Element {
  const [showConfig, setShowConfig] = useState(false)

  useEffect(() => {
    window.electronAPI.getToken().then(t => {
      if (!t) setShowConfig(true)
    })
  }, [])

  return (
    <div className="app-shell">
      <div className="top-bar">
        <StatusBar />
        <button
          className="config-btn"
          title="Settings"
          onClick={() => setShowConfig(s => !s)}
        >
          ⚙
        </button>
      </div>
      {showConfig ? (
        <ConfigScreen />
      ) : (
        <div className="main-panels">
          <FilePanel />
          <VisualizerPanel />
        </div>
      )}
    </div>
  )
}
