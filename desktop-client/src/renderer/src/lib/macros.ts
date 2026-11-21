export interface Macro {
  id: string
  name: string
  /** One MDI line per row. */
  gcode: string
  /** Ask for confirmation before running it. */
  confirm: boolean
}

const STORAGE_KEY = 'mcp-cnc.macros'

let counter = 0
export function newMacro(): Macro {
  return { id: `macro-${Date.now()}-${++counter}`, name: 'Nueva macro', gcode: '', confirm: true }
}

function isMacro(value: unknown): value is Macro {
  if (typeof value !== 'object' || value === null) return false
  const m = value as Record<string, unknown>
  return typeof m.id === 'string' && typeof m.name === 'string'
    && typeof m.gcode === 'string' && typeof m.confirm === 'boolean'
}

// localStorage can be missing or throw (private mode, blocked data): macros then just start empty.
export function loadMacros(): Macro[] {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed: unknown = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed.filter(isMacro) : []
  } catch {
    return []
  }
}

export function saveMacros(macros: Macro[]): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(macros))
  } catch {
    // not persisted; the macros still work for this session
  }
}

/** The MDI lines to send: blank lines and comment-only lines are dropped. */
export function gcodeLines(text: string): string[] {
  return text
    .split(/\r?\n/)
    .map(line => line.trim())
    .filter(line => line !== '' && !line.startsWith(';') && !/^\(.*\)$/.test(line))
}
