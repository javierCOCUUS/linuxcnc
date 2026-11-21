import { describe, it, expect } from 'vitest'
import { PANEL_DEFS, getPanelDef } from '../../src/renderer/src/lib/panels'
import { TEMPLATES, DEFAULT_TEMPLATE, getTemplate } from '../../src/renderer/src/lib/templates'

describe('panel registry', () => {
  it('has unique types and a title for every panel', () => {
    const types = PANEL_DEFS.map(d => d.type)
    expect(new Set(types).size).toBe(types.length)
    expect(PANEL_DEFS.every(d => d.title.length > 0)).toBe(true)
  })

  it('gives every panel a minimum size so it never collapses', () => {
    for (const def of PANEL_DEFS) {
      expect(def.minWidth).toBeGreaterThanOrEqual(200)
      expect(def.minHeight).toBeGreaterThanOrEqual(100)
    }
  })

  it('looks panels up by type', () => {
    expect(getPanelDef('jog-control')?.title).toBe('Jog Control')
    expect(getPanelDef('nope')).toBeUndefined()
  })
})

describe('templates', () => {
  it('defines the five standard tabs', () => {
    expect(TEMPLATES.map(t => t.label)).toEqual([
      'Operación', 'Puesta en marcha', 'Diagnóstico', 'Producción', 'CAM',
    ])
  })

  it.each(TEMPLATES.map(t => [t.id, t] as const))('%s only uses registered panels, once each', (_id, template) => {
    const types = template.panels.map(p => p.type)
    expect(types.every(t => getPanelDef(t) !== undefined)).toBe(true)
    expect(new Set(types).size).toBe(types.length)
  })

  it.each(TEMPLATES.map(t => [t.id, t] as const))('%s starts with an unplaced panel and splits only from panels already added', (_id, template) => {
    expect(template.panels[0].position).toBeUndefined()
    const added = new Set<string>()
    for (const panel of template.panels) {
      if (panel.position) expect(added.has(panel.position.of)).toBe(true)
      added.add(panel.type)
    }
  })

  it('adds the right-hand panel before the one below, so it spans the full height', () => {
    for (const template of TEMPLATES) {
      const firstBelow = template.panels.findIndex(p => p.position?.direction === 'below')
      const lastRight = template.panels.map(p => p.position?.direction).lastIndexOf('right')
      if (firstBelow >= 0 && lastRight >= 0) expect(lastRight).toBeLessThan(firstBelow)
    }
  })

  it('puts the jog control in the operation and commissioning tabs', () => {
    expect(getTemplate('operacion').panels.map(p => p.type)).toContain('jog-control')
    expect(getTemplate('puesta-en-marcha').panels.map(p => p.type)).toContain('jog-control')
  })

  it('falls back to the default template for an unknown id', () => {
    expect(getTemplate('does-not-exist').id).toBe(DEFAULT_TEMPLATE)
    expect(getTemplate(undefined).id).toBe(DEFAULT_TEMPLATE)
  })
})
