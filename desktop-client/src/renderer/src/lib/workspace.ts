import type { DockviewApi } from 'dockview'
import { getPanelDef } from './panels'
import type { Template } from './templates'

type Direction = 'right' | 'below' | 'within'
type Position = { referencePanel: string; direction: Direction } | undefined

function addPanel(api: DockviewApi, type: string, position: Position): void {
  const def = getPanelDef(type)
  if (!def) return
  // The id is the panel type: a tab never holds two panels of the same kind.
  api.addPanel({
    id: def.type,
    component: def.type,
    title: def.title,
    params: { type: def.type },
    minimumWidth: def.minWidth,
    minimumHeight: def.minHeight,
    ...(position ? { position } : {}),
  })
}

/** Builds a template's panels in an empty workspace. */
export function applyTemplate(api: DockviewApi, template: Template): void {
  for (const spec of template.panels) {
    addPanel(
      api,
      spec.type,
      spec.position ? { referencePanel: spec.position.of, direction: spec.position.direction } : undefined,
    )
  }
}

type GroupLike = {
  api?: { width?: number; height?: number }
  activePanel?: { id: string }
  panels?: { id: string }[]
}

function groupMins(group: GroupLike): { width: number; height: number } {
  let width = 0
  let height = 0
  for (const panel of group.panels ?? []) {
    const def = getPanelDef(panel.id)
    if (def) {
      width = Math.max(width, def.minWidth)
      height = Math.max(height, def.minHeight)
    }
  }
  return { width, height }
}

/**
 * Splitting halves the group, so both halves must still respect the minimum size of the
 * panel that is already there and of the new one. Otherwise dockview would squeeze
 * panels below their minimum, which is what clips their content.
 */
function splitFits(group: GroupLike, direction: 'right' | 'below', newType: string): boolean {
  const def = getPanelDef(newType)
  if (!def) return false
  const mins = groupMins(group)
  if (direction === 'right') {
    return (group.api?.width ?? 0) / 2 >= Math.max(def.minWidth, mins.width)
  }
  return (group.api?.height ?? 0) / 2 >= Math.max(def.minHeight, mins.height)
}

/**
 * Opens a panel. If the tab already has it, that panel is focused instead of duplicated.
 * Otherwise the biggest group that has room is split (to the right when it is wide, below
 * when it is tall). When no group has room, the panel joins the biggest group as a tab, so
 * nothing is ever squeezed below its minimum size.
 */
export function openPanel(api: DockviewApi, type: string): 'added' | 'focused' | 'unknown' {
  if (!getPanelDef(type)) return 'unknown'

  const existing = api.getPanel(type)
  if (existing) {
    existing.api.setActive()
    return 'focused'
  }

  const groups = [...((api.groups ?? []) as unknown as GroupLike[])]
  const area = (g: GroupLike): number => (g.api?.width ?? 0) * (g.api?.height ?? 0)
  groups.sort((a, b) => area(b) - area(a))

  let position: Position
  for (const group of groups) {
    const reference = group.activePanel?.id ?? group.panels?.[0]?.id
    if (!reference) continue
    const wide = (group.api?.width ?? 0) >= (group.api?.height ?? 0) * 1.2
    const order: ('right' | 'below')[] = wide ? ['right', 'below'] : ['below', 'right']
    const direction = order.find(d => splitFits(group, d, type))
    if (direction) {
      position = { referencePanel: reference, direction }
      break
    }
  }

  if (!position && groups.length > 0) {
    const reference = groups[0].activePanel?.id ?? groups[0].panels?.[0]?.id
    if (reference) position = { referencePanel: reference, direction: 'within' }
  }

  addPanel(api, type, position)
  return 'added'
}
