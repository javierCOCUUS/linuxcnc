const PANEL_LABELS: Record<string, string> = {
  'machine-status': 'Machine Status',
  'position-xyz':   'Position XYZ',
  'file-manager':   'File Manager',
  'visualizer':     'Visualizer',
  'dxf-cam':        'DXF / CAM',
  'gcode-editor':   'G-Code Editor',
}

interface PlaceholderPanelProps {
  type: string
}

export function PlaceholderPanel({ type }: PlaceholderPanelProps): JSX.Element {
  const label = PANEL_LABELS[type] ?? type
  return (
    <div className="placeholder-panel">
      <span className="placeholder-icon">⋯</span>
      <p className="placeholder-label">{label}</p>
      <p className="placeholder-hint">— available in a future phase —</p>
    </div>
  )
}
