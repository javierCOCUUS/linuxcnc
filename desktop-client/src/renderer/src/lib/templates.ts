import type { TemplateId } from '../types/layout'
import type { PanelType } from './panels'

export interface TemplatePanel {
  type: PanelType
  /** Where to split from. Omitted for the first panel of a template. */
  position?: { direction: 'right' | 'below'; of: PanelType }
}

export interface Template {
  id: TemplateId
  label: string
  panels: TemplatePanel[]
}

// Order matters for dockview: the panel on the right is added BEFORE the one below,
// so the right-hand panel spans the full height instead of sitting under one cell.
export const TEMPLATES: Template[] = [
  {
    id: 'operacion',
    label: 'Operación',
    panels: [
      { type: 'machine-status' },
      { type: 'jog-control', position: { direction: 'right', of: 'machine-status' } },
      { type: 'position-xyz', position: { direction: 'below', of: 'machine-status' } },
    ],
  },
  {
    id: 'puesta-en-marcha',
    label: 'Puesta en marcha',
    panels: [
      { type: 'io-inputs' },
      { type: 'jog-control', position: { direction: 'right', of: 'io-inputs' } },
      { type: 'machine-status', position: { direction: 'below', of: 'io-inputs' } },
    ],
  },
  {
    id: 'diagnostico',
    label: 'Diagnóstico',
    panels: [
      { type: 'diagnostic' },
      { type: 'io-inputs', position: { direction: 'right', of: 'diagnostic' } },
      { type: 'services', position: { direction: 'below', of: 'diagnostic' } },
      { type: 'alarms', position: { direction: 'below', of: 'io-inputs' } },
    ],
  },
  {
    id: 'produccion',
    label: 'Producción',
    panels: [
      { type: 'machine-status' },
      { type: 'file-manager', position: { direction: 'right', of: 'machine-status' } },
      { type: 'position-xyz', position: { direction: 'below', of: 'machine-status' } },
    ],
  },
  {
    id: 'cam',
    label: 'CAM',
    panels: [
      { type: 'dxf-cam' },
      { type: 'visualizer', position: { direction: 'right', of: 'dxf-cam' } },
      { type: 'gcode-editor', position: { direction: 'below', of: 'dxf-cam' } },
    ],
  },
]

export const DEFAULT_TEMPLATE: TemplateId = 'operacion'

export function getTemplate(id: string | undefined): Template {
  return TEMPLATES.find(t => t.id === id) ?? TEMPLATES.find(t => t.id === DEFAULT_TEMPLATE)!
}
