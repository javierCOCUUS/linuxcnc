// Electron wraps main-process errors: "Error invoking remote method 'x': Error: <detail>".
export function cleanError(err: unknown): string {
  const raw = err instanceof Error ? err.message : String(err)
  return raw.replace(/^Error invoking remote method '[^']+': (Error: )?/, '')
}
