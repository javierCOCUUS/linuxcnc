import { useState } from 'react'

const PANEL_OPTIONS = [
  { type: 'machine-status', title: 'Machine Status' },
  { type: 'position-xyz',   title: 'Position XYZ' },
  { type: 'diagnostic',     title: 'E-stop / HAL' },
  { type: 'alarms',         title: 'Alarmas' },
  { type: 'file-manager',   title: 'File Manager' },
  { type: 'visualizer',     title: 'Visualizer' },
  { type: 'dxf-cam',        title: 'DXF / CAM' },
  { type: 'gcode-editor',   title: 'G-Code Editor' },
  { type: 'config',         title: 'Settings' },
]

interface PanelPickerProps {
  onAddPanel: (panel: { type: string; title: string }) => void
}

export function PanelPicker({ onAddPanel }: PanelPickerProps): JSX.Element {
  const [open, setOpen] = useState(false)

  function handleSelect(option: { type: string; title: string }): void {
    onAddPanel(option)
    setOpen(false)
  }

  return (
    <div className="panel-picker">
      <button
        className="panel-picker-btn"
        onClick={() => setOpen(o => !o)}
        aria-label="Add panel"
      >
        Add panel
      </button>
      {open && (
        <ul className="panel-picker-menu" role="menu">
          {PANEL_OPTIONS.map(opt => (
            <li
              key={opt.type}
              role="menuitem"
              className="panel-picker-option"
              onClick={() => handleSelect(opt)}
            >
              {opt.title}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
