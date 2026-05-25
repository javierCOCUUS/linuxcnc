import { useState, useEffect } from 'react'
import type { WorkspaceFile } from '../types/api'

export function FilePanel(): JSX.Element {
  const [files, setFiles] = useState<WorkspaceFile[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    window.electronAPI.listFiles()
      .then(data => setFiles(data))
      .catch(err => setError(String(err)))
  }, [])

  if (error) return <div className="file-panel file-panel--error">{error}</div>
  if (!files) return <div className="file-panel">Loading...</div>
  if (files.length === 0) return <div className="file-panel">No files in workspace</div>

  return (
    <div className="file-panel">
      <h3>Workspace</h3>
      <ul className="file-list">
        {files.map(f => (
          <li key={f.name} className="file-item">
            <span className="file-name">{f.name}</span>
            <span className="file-size">{(f.size / 1024).toFixed(1)} KB</span>
          </li>
        ))}
      </ul>
    </div>
  )
}
