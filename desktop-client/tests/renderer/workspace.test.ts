import { describe, it, expect, vi } from 'vitest'
import type { DockviewApi } from 'dockview'
import { applyTemplate, openPanel } from '../../src/renderer/src/lib/workspace'
import { getTemplate } from '../../src/renderer/src/lib/templates'
import { getPanelDef } from '../../src/renderer/src/lib/panels'

type Group = {
  api: { width: number; height: number }
  activePanel?: { id: string }
  panels: { id: string }[]
}

const g = (width: number, height: number, ...ids: string[]): Group => ({
  api: { width, height },
  activePanel: { id: ids[0] },
  panels: ids.map(id => ({ id })),
})

function fakeApi(existing: string[] = [], groups: Group[] = []) {
  const panels = new Map<string, { api: { setActive: ReturnType<typeof vi.fn> } }>()
  existing.forEach(id => panels.set(id, { api: { setActive: vi.fn() } }))
  const api = {
    addPanel: vi.fn((opts: { id: string }) => { panels.set(opts.id, { api: { setActive: vi.fn() } }) }),
    getPanel: vi.fn((id: string) => panels.get(id)),
    groups,
  }
  return { api: api as unknown as DockviewApi, mock: api, panels }
}

describe('applyTemplate', () => {
  it('adds each panel with the type as id, component and params', () => {
    const { api, mock } = fakeApi()
    applyTemplate(api, getTemplate('operacion'))
    expect(mock.addPanel).toHaveBeenCalledTimes(3)
    for (const [opts] of mock.addPanel.mock.calls as [Record<string, unknown>][]) {
      expect(opts.id).toBe(opts.component)
      expect(opts.params).toEqual({ type: opts.id })
    }
  })

  it('sets each panel minimum size from the registry', () => {
    const { api, mock } = fakeApi()
    applyTemplate(api, getTemplate('operacion'))
    const jog = mock.addPanel.mock.calls.map(c => c[0] as Record<string, unknown>).find(o => o.id === 'jog-control')!
    expect(jog.minimumWidth).toBe(getPanelDef('jog-control')!.minWidth)
    expect(jog.minimumHeight).toBe(getPanelDef('jog-control')!.minHeight)
  })

  it('places panels relative to ones already added', () => {
    const { api, mock } = fakeApi()
    applyTemplate(api, getTemplate('operacion'))
    const calls = mock.addPanel.mock.calls.map(c => c[0] as { id: string; position?: unknown })
    expect(calls[0].position).toBeUndefined()
    expect(calls[1]).toMatchObject({ id: 'jog-control', position: { referencePanel: 'machine-status', direction: 'right' } })
    expect(calls[2]).toMatchObject({ id: 'position-xyz', position: { referencePanel: 'machine-status', direction: 'below' } })
  })
})

describe('openPanel', () => {
  it('focuses a panel the tab already has instead of duplicating it', () => {
    const { api, mock, panels } = fakeApi(['jog-control'])
    expect(openPanel(api, 'jog-control')).toBe('focused')
    expect(mock.addPanel).not.toHaveBeenCalled()
    expect(panels.get('jog-control')!.api.setActive).toHaveBeenCalledTimes(1)
  })

  it('adds a panel that is not there yet', () => {
    const { api, mock } = fakeApi()
    expect(openPanel(api, 'alarms')).toBe('added')
    expect(mock.addPanel).toHaveBeenCalledTimes(1)
    expect(mock.addPanel.mock.calls[0][0]).toMatchObject({ id: 'alarms', params: { type: 'alarms' } })
  })

  it('ignores a type that is not registered', () => {
    const { api, mock } = fakeApi()
    expect(openPanel(api, 'nope')).toBe('unknown')
    expect(mock.addPanel).not.toHaveBeenCalled()
  })

  it('splits the biggest group, to the right when it is wide', () => {
    const groups: Group[] = [
      { api: { width: 300, height: 300 }, activePanel: { id: 'small' }, panels: [{ id: 'small' }] },
      { api: { width: 900, height: 400 }, activePanel: { id: 'wide' }, panels: [{ id: 'wide' }] },
    ]
    const { api, mock } = fakeApi([], groups)
    openPanel(api, 'alarms')
    expect(mock.addPanel.mock.calls[0][0]).toMatchObject({
      position: { referencePanel: 'wide', direction: 'right' },
    })
  })

  it('splits the biggest group below when it is tall', () => {
    const groups: Group[] = [
      { api: { width: 300, height: 700 }, activePanel: { id: 'tall' }, panels: [{ id: 'tall' }] },
    ]
    const { api, mock } = fakeApi([], groups)
    openPanel(api, 'alarms')
    expect(mock.addPanel.mock.calls[0][0]).toMatchObject({
      position: { referencePanel: 'tall', direction: 'below' },
    })
  })

  it('falls back to the first panel of a group with no active panel', () => {
    const groups: Group[] = [{ api: { width: 500, height: 500 }, panels: [{ id: 'first' }] }]
    const { api, mock } = fakeApi([], groups)
    openPanel(api, 'alarms')
    expect(mock.addPanel.mock.calls[0][0]).toMatchObject({ position: { referencePanel: 'first' } })
  })

  it('adds without a position when the workspace is empty', () => {
    const { api, mock } = fakeApi()
    openPanel(api, 'alarms')
    expect((mock.addPanel.mock.calls[0][0] as { position?: unknown }).position).toBeUndefined()
  })

  describe('when there is little room', () => {
    it('does not split a group that would end up below the minimum width', () => {
      // 500 wide: halves of 250 < the 260 minimum of alarms -> cannot split right
      const { api, mock } = fakeApi([], [g(500, 900, 'alarms')])
      openPanel(api, 'services')
      // wide? no (tall) -> tries below first: 450 >= 140 -> fits below
      expect(mock.addPanel.mock.calls[0][0]).toMatchObject({ position: { direction: 'below' } })
    })

    it('tries the other direction when the preferred one does not fit', () => {
      // wide group, but halves of 250 are below the 260 minimum -> falls back to below
      const { api, mock } = fakeApi([], [g(500, 380, 'alarms')])
      openPanel(api, 'services')
      expect(mock.addPanel.mock.calls[0][0]).toMatchObject({
        position: { referencePanel: 'alarms', direction: 'below' },
      })
    })

    it('uses the next biggest group when the biggest has no room', () => {
      // biggest by area (125k) but neither half fits: 250 < 260 wide, 125 < 140 tall
      const cramped = g(500, 250, 'alarms')
      // smaller (105k), wide and short: splitting right gives 350 >= 260
      const roomy = g(700, 150, 'services')
      const { api, mock } = fakeApi([], [cramped, roomy])
      openPanel(api, 'file-manager')
      expect(mock.addPanel.mock.calls[0][0]).toMatchObject({
        position: { referencePanel: 'services', direction: 'right' },
      })
    })

    it('adds the panel as a tab of the biggest group when nothing has room', () => {
      const groups = [g(400, 250, 'alarms'), g(380, 240, 'services')]
      const { api, mock } = fakeApi([], groups)
      openPanel(api, 'file-manager')
      expect(mock.addPanel.mock.calls[0][0]).toMatchObject({
        id: 'file-manager',
        position: { referencePanel: 'alarms', direction: 'within' },
      })
    })

    it('respects the minimum of every panel already tabbed in the group', () => {
      // the group holds jog-control (min width 320): halves of 300 do not fit
      const { api, mock } = fakeApi([], [g(600, 380, 'jog-control')])
      openPanel(api, 'services')
      expect(mock.addPanel.mock.calls[0][0]).toMatchObject({ position: { direction: 'within' } })
    })
  })
})

