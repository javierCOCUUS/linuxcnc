import { useState } from 'react'
import { PANEL_DEFS } from '../lib/panels'

const PANEL_OPTIONS = PANEL_DEFS.map(def => ({ type: def.type, title: def.title }))

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
