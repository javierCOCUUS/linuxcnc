export type PanelType =
  | 'machine-status'
  | 'position-xyz'
  | 'jog-control'
  | 'spindle'
  | 'macros'
  | 'io-inputs'
  | 'diagnostic'
  | 'alarms'
  | 'file-manager'
  | 'services'
  | 'visualizer'
  | 'dxf-cam'
  | 'gcode-editor'
  | 'config'

export interface PanelDef {
  type: PanelType
  title: string
  /** Smallest size, in px, at which the panel still shows all its controls. */
  minWidth: number
  minHeight: number
}

/** Every panel the app can open, in the order the "Add panel" menu lists them. */
export const PANEL_DEFS: PanelDef[] = [
  { type: 'machine-status', title: 'Machine Status', minWidth: 240, minHeight: 150 },
  { type: 'position-xyz',   title: 'Position XYZ',   minWidth: 240, minHeight: 130 },
  { type: 'jog-control',    title: 'Jog Control',    minWidth: 320, minHeight: 400 },
  { type: 'spindle',       title: 'Spindle',        minWidth: 280, minHeight: 260 },
  { type: 'macros',        title: 'Macros',         minWidth: 280, minHeight: 200 },
  { type: 'io-inputs',      title: 'I/O Inputs',     minWidth: 280, minHeight: 140 },
  { type: 'diagnostic',     title: 'E-stop / HAL',   minWidth: 260, minHeight: 170 },
  { type: 'alarms',         title: 'Alarmas',        minWidth: 260, minHeight: 140 },
  { type: 'file-manager',   title: 'File Manager',   minWidth: 260, minHeight: 160 },
  { type: 'services',       title: 'Services',       minWidth: 240, minHeight: 110 },
  { type: 'visualizer',     title: 'Visualizer',     minWidth: 320, minHeight: 240 },
  { type: 'dxf-cam',        title: 'DXF / CAM',      minWidth: 280, minHeight: 200 },
  { type: 'gcode-editor',   title: 'G-Code Editor',  minWidth: 280, minHeight: 200 },
  { type: 'config',         title: 'Settings',       minWidth: 320, minHeight: 260 },
]

export function getPanelDef(type: string): PanelDef | undefined {
  return PANEL_DEFS.find(def => def.type === type)
}
