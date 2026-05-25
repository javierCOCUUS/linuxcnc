# Machine Status Panel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the `machine-status` placeholder panel with a real read-only panel that polls `getMachineStatus()` every 2 seconds, pauses on hide/blur, resumes with an immediate fetch, marks stale after 2 failures, and renders gracefully on partial data.

**Architecture:** `useMachineStatus` hook owns the entire polling lifecycle (interval + visibility + focus events). `MachineStatusPanel` calls the hook and renders — it contains zero polling code. `AppShell` routes dockview component type `'machine-status'` to the new panel; all other types keep `PlaceholderPanel`.

**Tech Stack:** React 18, TypeScript 5.4, Vitest + @testing-library/react, Electron IPC (`getMachineStatus` already wired), dockview v4. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-05-22-machine-status-panel-design.md`

**All commands run from:** `desktop-client/`

---

## File map

| File | Action |
|---|---|
| `src/renderer/src/types/api.ts` | Modify — replace `MachineStatus` with real backend shape |
| `src/renderer/src/hooks/useMachineStatus.ts` | Create |
| `src/renderer/src/components/panels/MachineStatusPanel.tsx` | Create |
| `src/renderer/src/components/AppShell.tsx` | Modify — add component entry + route by type |
| `src/renderer/src/App.css` | Modify — append panel CSS |
| `tests/renderer/hooks/useMachineStatus.test.ts` | Create |
| `tests/renderer/MachineStatusPanel.test.tsx` | Create |

**Never touch:** `ipc-handlers.ts`, `preload/index.ts`, `electron-api.d.ts`, anything in `linuxcnc-bridge/`, `mcp/`, `dxf-engine/`, `docker-compose.yml`, or any panel other than `machine-status`.

---

## Task 1: Fix MachineStatus type

**Files:**
- Modify: `desktop-client/src/renderer/src/types/api.ts`

The existing type was written speculatively and does not match the real bridge response. The real response shape (from `linuxcnc-bridge/main.py::_stub_status`):

```json
{
  "state": "IDLE",
  "position": {"x": 0.0, "y": 0.0, "z": 10.0},
  "homed": ["X", "Y", "Z"],
  "spindle": {"on": false, "speed": 0, "direction": "off"},
  "feed_rate": 100.0,
  "active_gcode": "G54 G17 G90",
  "system": {"backend": "stub", "cpu": "arm64", "temp": 45.2}
}
```

- [ ] **Step 1: Replace the MachineStatus interface**

Full replacement for `desktop-client/src/renderer/src/types/api.ts`:

```typescript
export interface MachineStatus {
  state: 'IDLE' | 'RUN' | 'PAUSED' | 'ESTOP' | 'UNAVAILABLE' | 'MDI'
  position: { x: number; y: number; z: number }
  homed: string[]
  spindle: { on: boolean; speed: number; direction: string }
  feed_rate: number
  active_gcode: string
  system: {
    backend: 'stub' | 'linuxcncrsh'
    error?: string
    [key: string]: unknown
  }
}

export interface WorkspaceFile {
  name: string
  size: number
  modified: number
}
```

- [ ] **Step 2: Run the full existing test suite — all 65 must pass**

```
npm test -- --reporter=verbose
```

Expected: `65 passed (65)` — no existing test constructs a `MachineStatus` object with the removed fields (`backend`, `tool`, `feed`, `units`, `spindle.state`).

- [ ] **Step 3: Commit**

```
git add src/renderer/src/types/api.ts
git commit -m "fix(types): align MachineStatus with real bridge API response"
```

---

## Task 2: useMachineStatus hook (TDD)

**Files:**
- Create: `desktop-client/tests/renderer/hooks/useMachineStatus.test.ts`
- Create: `desktop-client/src/renderer/src/hooks/useMachineStatus.ts`

**Run only these tests:**
```
npm test -- tests/renderer/hooks/useMachineStatus.test.ts --reporter=verbose
```

**Critical rule (Gotcha 1 + 2):** All polling lives inside `useEffect`. The cleanup function must clear the interval AND remove all three event listeners (`visibilitychange`, `focus`, `blur`). The interval accumulation test (test 8) verifies this directly.

- [ ] **Step 1: Create test directory and test file**

Create `desktop-client/tests/renderer/hooks/useMachineStatus.test.ts`:

```typescript
import { renderHook, act } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useMachineStatus } from '../../../src/renderer/src/hooks/useMachineStatus'

const mockStatus = {
  state: 'IDLE' as const,
  position: { x: 0, y: 0, z: 10 },
  homed: ['X', 'Y', 'Z'],
  spindle: { on: false, speed: 0, direction: 'off' },
  feed_rate: 100,
  active_gcode: 'G54 G17 G90',
  system: { backend: 'stub' as const },
}

function mockAPI(impl: () => Promise<unknown>): void {
  Object.defineProperty(window, 'electronAPI', {
    value: { getMachineStatus: vi.fn(impl) },
    writable: true,
    configurable: true,
  })
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
let hiddenSpy: any
// eslint-disable-next-line @typescript-eslint/no-explicit-any
let focusSpy: any

beforeEach(() => {
  vi.useFakeTimers()
  hiddenSpy = vi.spyOn(document, 'hidden', 'get').mockReturnValue(false)
  focusSpy = vi.spyOn(document, 'hasFocus').mockReturnValue(true)
  mockAPI(() => Promise.resolve(mockStatus))
})

afterEach(() => {
  vi.useRealTimers()
  vi.clearAllMocks()
  hiddenSpy?.mockRestore()
  focusSpy?.mockRestore()
})

describe('useMachineStatus', () => {
  it('fires an immediate fetch on mount and sets data', async () => {
    const { result } = renderHook(() => useMachineStatus())

    expect(result.current.loading).toBe(true)
    expect(result.current.data).toBeNull()

    await act(async () => { await Promise.resolve() })

    expect(result.current.loading).toBe(false)
    expect(result.current.data).toEqual(mockStatus)
    expect(window.electronAPI.getMachineStatus).toHaveBeenCalledTimes(1)
  })

  it('fires a second fetch after 2000 ms', async () => {
    renderHook(() => useMachineStatus())
    await act(async () => { await Promise.resolve() }) // first fetch

    await act(async () => {
      vi.advanceTimersByTime(2000)
      await Promise.resolve()
    })

    expect(window.electronAPI.getMachineStatus).toHaveBeenCalledTimes(2)
  })

  it('sets stale after 2 consecutive fetch failures', async () => {
    mockAPI(() => Promise.reject(new Error('network error')))

    const { result } = renderHook(() => useMachineStatus())

    await act(async () => { await Promise.resolve() }) // failure 1
    expect(result.current.stale).toBe(false)
    expect(result.current.error).toBe('network error')

    await act(async () => {
      vi.advanceTimersByTime(2000)
      await Promise.resolve()
    }) // failure 2
    expect(result.current.stale).toBe(true)
  })

  it('clears stale and error after a successful fetch', async () => {
    const mockFn = vi.fn()
      .mockRejectedValueOnce(new Error('fail'))
      .mockRejectedValueOnce(new Error('fail'))
      .mockResolvedValue(mockStatus)
    mockAPI(mockFn)

    const { result } = renderHook(() => useMachineStatus())

    await act(async () => { await Promise.resolve() })
    await act(async () => { vi.advanceTimersByTime(2000); await Promise.resolve() })
    expect(result.current.stale).toBe(true)

    await act(async () => { vi.advanceTimersByTime(2000); await Promise.resolve() }) // success
    expect(result.current.stale).toBe(false)
    expect(result.current.error).toBeNull()
    expect(result.current.data).toEqual(mockStatus)
  })

  it('pauses polling when document becomes hidden', async () => {
    renderHook(() => useMachineStatus())
    await act(async () => { await Promise.resolve() }) // first fetch

    hiddenSpy.mockReturnValue(true)
    act(() => { document.dispatchEvent(new Event('visibilitychange')) })

    await act(async () => { vi.advanceTimersByTime(6000); await Promise.resolve() })

    // Only the one immediate fetch from mount — nothing after hidden
    expect(window.electronAPI.getMachineStatus).toHaveBeenCalledTimes(1)
  })

  it('fires an immediate fetch when becoming visible again', async () => {
    hiddenSpy.mockReturnValue(true)
    renderHook(() => useMachineStatus())

    await act(async () => { await Promise.resolve() })
    expect(window.electronAPI.getMachineStatus).toHaveBeenCalledTimes(0) // hidden on mount

    hiddenSpy.mockReturnValue(false)
    await act(async () => {
      document.dispatchEvent(new Event('visibilitychange'))
      await Promise.resolve()
    })

    expect(window.electronAPI.getMachineStatus).toHaveBeenCalledTimes(1)
  })

  it('stops polling after unmount', async () => {
    const { unmount } = renderHook(() => useMachineStatus())
    await act(async () => { await Promise.resolve() })

    unmount()

    await act(async () => { vi.advanceTimersByTime(6000); await Promise.resolve() })

    expect(window.electronAPI.getMachineStatus).toHaveBeenCalledTimes(1)
  })

  it('does not accumulate intervals across unmount and remount (Gotcha 2)', async () => {
    const { unmount } = renderHook(() => useMachineStatus())
    await act(async () => { await Promise.resolve() })
    expect(window.electronAPI.getMachineStatus).toHaveBeenCalledTimes(1) // mount 1 immediate

    unmount()

    renderHook(() => useMachineStatus())
    await act(async () => { await Promise.resolve() })
    expect(window.electronAPI.getMachineStatus).toHaveBeenCalledTimes(2) // mount 2 immediate

    // Advance 2000 ms — only ONE interval active (mount 2's), not two
    await act(async () => { vi.advanceTimersByTime(2000); await Promise.resolve() })
    expect(window.electronAPI.getMachineStatus).toHaveBeenCalledTimes(3) // exactly 3, not 4
  })

  it('pauses polling on window blur and resumes with immediate fetch on focus', async () => {
    renderHook(() => useMachineStatus())
    await act(async () => { await Promise.resolve() }) // mount immediate
    expect(window.electronAPI.getMachineStatus).toHaveBeenCalledTimes(1)

    act(() => { window.dispatchEvent(new Event('blur')) })
    await act(async () => { vi.advanceTimersByTime(4000); await Promise.resolve() })
    expect(window.electronAPI.getMachineStatus).toHaveBeenCalledTimes(1) // paused

    await act(async () => {
      window.dispatchEvent(new Event('focus'))
      await Promise.resolve()
    })
    expect(window.electronAPI.getMachineStatus).toHaveBeenCalledTimes(2) // immediate on resume
  })
})
```

- [ ] **Step 2: Run test — verify it fails**

```
npm test -- tests/renderer/hooks/useMachineStatus.test.ts --reporter=verbose
```

Expected: FAIL — `Cannot find module '.../hooks/useMachineStatus'`

- [ ] **Step 3: Create the hook**

Create `desktop-client/src/renderer/src/hooks/useMachineStatus.ts`:

```typescript
import { useState, useEffect } from 'react'
import type { MachineStatus } from '../types/api'

export interface UseMachineStatusResult {
  data: MachineStatus | null
  error: string | null
  stale: boolean
  loading: boolean
}

export function useMachineStatus(): UseMachineStatusResult {
  const [data, setData] = useState<MachineStatus | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [stale, setStale] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let intervalId: ReturnType<typeof setInterval> | null = null
    let mounted = true
    let failCount = 0

    async function fetchStatus(): Promise<void> {
      if (!mounted) return
      try {
        const result = await window.electronAPI.getMachineStatus()
        if (!mounted) return
        setData(result as MachineStatus)
        setError(null)
        failCount = 0
        setStale(false)
        setLoading(false)
      } catch (err) {
        if (!mounted) return
        failCount += 1
        setError(err instanceof Error ? err.message : 'Unknown error')
        if (failCount >= 2) setStale(true)
        setLoading(false)
      }
    }

    function clearPoll(): void {
      if (intervalId !== null) {
        clearInterval(intervalId)
        intervalId = null
      }
    }

    function startPoll(): void {
      clearPoll()
      void fetchStatus()
      intervalId = setInterval(() => { void fetchStatus() }, 2000)
    }

    function onVisibilityChange(): void {
      if (document.hidden) { clearPoll() } else { startPoll() }
    }

    function onFocus(): void { startPoll() }
    function onBlur(): void { clearPoll() }

    if (!document.hidden && document.hasFocus()) {
      startPoll()
    }

    document.addEventListener('visibilitychange', onVisibilityChange)
    window.addEventListener('focus', onFocus)
    window.addEventListener('blur', onBlur)

    return () => {
      mounted = false
      clearPoll()
      document.removeEventListener('visibilitychange', onVisibilityChange)
      window.removeEventListener('focus', onFocus)
      window.removeEventListener('blur', onBlur)
    }
  }, [])

  return { data, error, stale, loading }
}
```

- [ ] **Step 4: Run hook tests — all 9 must pass**

```
npm test -- tests/renderer/hooks/useMachineStatus.test.ts --reporter=verbose
```

Expected: `9 passed (9)`

- [ ] **Step 5: Run full suite — existing 65 still pass**

```
npm test -- --reporter=verbose
```

Expected: `74 passed (74)`

- [ ] **Step 6: Commit**

```
git add src/renderer/src/hooks/useMachineStatus.ts \
        tests/renderer/hooks/useMachineStatus.test.ts
git commit -m "feat(desktop): add useMachineStatus polling hook with visibility/focus pausing"
```

---

## Task 3: MachineStatusPanel component (TDD)

**Files:**
- Create: `desktop-client/tests/renderer/MachineStatusPanel.test.tsx`
- Create: `desktop-client/src/renderer/src/components/panels/MachineStatusPanel.tsx`

**Run only these tests:**
```
npm test -- tests/renderer/MachineStatusPanel.test.tsx --reporter=verbose
```

**Critical (Gotcha 1):** The panel must contain NO `setInterval`, `setTimeout`, `useEffect`, or direct `window.electronAPI` calls. It calls `useMachineStatus()` and renders only.

**Critical (Gotcha 3):** Every field access uses `?.` and `?? '—'`. Test 15 verifies this by passing `spindle: undefined` and `feed_rate: undefined` and asserting no throw.

- [ ] **Step 1: Create the test file**

Create `desktop-client/tests/renderer/MachineStatusPanel.test.tsx`:

```typescript
import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { MachineStatusPanel } from '../../../src/renderer/src/components/panels/MachineStatusPanel'
import * as hook from '../../../src/renderer/src/hooks/useMachineStatus'
import type { UseMachineStatusResult } from '../../../src/renderer/src/hooks/useMachineStatus'

vi.mock('../../../src/renderer/src/hooks/useMachineStatus')

function makeResult(overrides: Partial<UseMachineStatusResult> = {}): UseMachineStatusResult {
  return { data: null, error: null, stale: false, loading: false, ...overrides }
}

const idleStatus = {
  state: 'IDLE' as const,
  position: { x: 1, y: 2, z: 3 },
  homed: ['X', 'Y', 'Z'],
  spindle: { on: false, speed: 0, direction: 'off' },
  feed_rate: 100,
  active_gcode: 'G54 G17 G90',
  system: { backend: 'stub' as const },
}

beforeEach(() => {
  vi.mocked(hook.useMachineStatus).mockReturnValue(makeResult())
})

describe('MachineStatusPanel', () => {
  it('shows — placeholders while loading', () => {
    vi.mocked(hook.useMachineStatus).mockReturnValue(makeResult({ loading: true }))
    render(<MachineStatusPanel />)
    expect(screen.getAllByText('—').length).toBeGreaterThan(0)
  })

  it('renders IDLE state badge', () => {
    vi.mocked(hook.useMachineStatus).mockReturnValue(makeResult({ data: idleStatus }))
    render(<MachineStatusPanel />)
    expect(screen.getByText('IDLE')).toBeInTheDocument()
  })

  it('renders RUN state badge', () => {
    vi.mocked(hook.useMachineStatus).mockReturnValue(
      makeResult({ data: { ...idleStatus, state: 'RUN' } })
    )
    render(<MachineStatusPanel />)
    expect(screen.getByText('RUN')).toBeInTheDocument()
  })

  it('renders ESTOP state badge', () => {
    vi.mocked(hook.useMachineStatus).mockReturnValue(
      makeResult({ data: { ...idleStatus, state: 'ESTOP' } })
    )
    render(<MachineStatusPanel />)
    expect(screen.getByText('ESTOP')).toBeInTheDocument()
  })

  it('shows spindle OFF when spindle.on is false', () => {
    vi.mocked(hook.useMachineStatus).mockReturnValue(makeResult({ data: idleStatus }))
    render(<MachineStatusPanel />)
    expect(screen.getByText(/OFF/i)).toBeInTheDocument()
  })

  it('shows spindle ON with speed and direction', () => {
    vi.mocked(hook.useMachineStatus).mockReturnValue(
      makeResult({ data: { ...idleStatus, spindle: { on: true, speed: 12000, direction: 'CW' } } })
    )
    render(<MachineStatusPanel />)
    expect(screen.getByText(/12000/)).toBeInTheDocument()
    expect(screen.getByText(/CW/)).toBeInTheDocument()
  })

  it('shows feed rate', () => {
    vi.mocked(hook.useMachineStatus).mockReturnValue(makeResult({ data: idleStatus }))
    render(<MachineStatusPanel />)
    expect(screen.getByText(/100/)).toBeInTheDocument()
  })

  it('shows homed axes as space-separated string', () => {
    vi.mocked(hook.useMachineStatus).mockReturnValue(makeResult({ data: idleStatus }))
    render(<MachineStatusPanel />)
    expect(screen.getByText('X Y Z')).toBeInTheDocument()
  })

  it('shows None when homed array is empty', () => {
    vi.mocked(hook.useMachineStatus).mockReturnValue(
      makeResult({ data: { ...idleStatus, homed: [] } })
    )
    render(<MachineStatusPanel />)
    expect(screen.getByText(/none/i)).toBeInTheDocument()
  })

  it('shows active G-code', () => {
    vi.mocked(hook.useMachineStatus).mockReturnValue(makeResult({ data: idleStatus }))
    render(<MachineStatusPanel />)
    expect(screen.getByText('G54 G17 G90')).toBeInTheDocument()
  })

  it('shows error banner when system.error is set', () => {
    vi.mocked(hook.useMachineStatus).mockReturnValue(
      makeResult({
        data: {
          ...idleStatus,
          state: 'UNAVAILABLE',
          system: { backend: 'linuxcncrsh', error: 'Connection refused' },
        },
      })
    )
    render(<MachineStatusPanel />)
    expect(screen.getByRole('alert')).toHaveTextContent('Connection refused')
  })

  it('does not show error banner when system.error is absent', () => {
    vi.mocked(hook.useMachineStatus).mockReturnValue(makeResult({ data: idleStatus }))
    render(<MachineStatusPanel />)
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('appends (stale) to state text when stale is true', () => {
    vi.mocked(hook.useMachineStatus).mockReturnValue(
      makeResult({ data: idleStatus, stale: true })
    )
    render(<MachineStatusPanel />)
    expect(screen.getByText(/stale/i)).toBeInTheDocument()
  })

  it('shows fetch error message when data is null and error is set', () => {
    vi.mocked(hook.useMachineStatus).mockReturnValue(makeResult({ error: 'HTTP 503' }))
    render(<MachineStatusPanel />)
    expect(screen.getByText(/HTTP 503/)).toBeInTheDocument()
  })

  it('does not crash when backend returns partial data — Gotcha 3', () => {
    vi.mocked(hook.useMachineStatus).mockReturnValue(
      makeResult({
        data: {
          state: 'UNAVAILABLE',
          position: { x: 0, y: 0, z: 0 },
          homed: [],
          spindle: undefined as unknown as { on: boolean; speed: number; direction: string },
          feed_rate: undefined as unknown as number,
          active_gcode: undefined as unknown as string,
          system: { backend: 'linuxcncrsh' },
        },
      })
    )
    expect(() => render(<MachineStatusPanel />)).not.toThrow()
  })
})
```

- [ ] **Step 2: Run test — verify it fails**

```
npm test -- tests/renderer/MachineStatusPanel.test.tsx --reporter=verbose
```

Expected: FAIL — `Cannot find module '.../MachineStatusPanel'`

- [ ] **Step 3: Create the panel component**

Create `desktop-client/src/renderer/src/components/panels/MachineStatusPanel.tsx`:

```typescript
import { useMachineStatus } from '../../hooks/useMachineStatus'

const STATE_COLORS: Record<string, string> = {
  IDLE:        '#22c55e',
  RUN:         '#00aaff',
  PAUSED:      '#f59e0b',
  MDI:         '#a855f7',
  ESTOP:       '#ff4444',
  UNAVAILABLE: '#666',
}

export function MachineStatusPanel(): JSX.Element {
  const { data, error, stale, loading } = useMachineStatus()

  if (loading && !data && !error) {
    return (
      <div className="machine-status-panel">
        <div className="ms-state-badge" style={{ color: '#666' }}>—</div>
        <div className="ms-row"><span className="ms-label">Spindle</span><span>—</span></div>
        <div className="ms-row"><span className="ms-label">Feed</span><span>—</span></div>
        <div className="ms-row"><span className="ms-label">Homed</span><span>—</span></div>
        <div className="ms-row"><span className="ms-label">G-code</span><span>—</span></div>
      </div>
    )
  }

  if (!data && error) {
    return (
      <div className="machine-status-panel">
        <div className="ms-error" role="alert">{error}</div>
      </div>
    )
  }

  const stateText = stale ? `${data?.state ?? '—'} (stale)` : (data?.state ?? '—')
  const stateColor = STATE_COLORS[data?.state ?? ''] ?? '#666'
  const stateOpacity = stale ? 0.5 : 1

  const spindleOn = data?.spindle?.on
  const spindleText = spindleOn
    ? `ON  ${data?.spindle?.speed ?? 0} rpm  ${data?.spindle?.direction ?? ''}`
    : 'OFF'

  const feedText = data?.feed_rate != null ? `${data.feed_rate}%` : '—'
  const homedText = (data?.homed?.length ?? 0) > 0
    ? (data?.homed ?? []).join(' ')
    : 'None'
  const gcodeText = data?.active_gcode ?? '—'
  const backendText = data?.system?.backend ?? ''
  const systemError = data?.system?.error

  return (
    <div className="machine-status-panel">
      <div className="ms-header">
        <span
          className="ms-state-badge"
          style={{ color: stateColor, opacity: stateOpacity }}
        >
          {stateText}
        </span>
        {backendText && <span className="ms-backend">{backendText}</span>}
      </div>
      <div className="ms-row">
        <span className="ms-label">Spindle</span>
        <span>{spindleText}</span>
      </div>
      <div className="ms-row">
        <span className="ms-label">Feed</span>
        <span>{feedText}</span>
      </div>
      <div className="ms-row">
        <span className="ms-label">Homed</span>
        <span>{homedText}</span>
      </div>
      <div className="ms-row">
        <span className="ms-label">G-code</span>
        <span>{gcodeText}</span>
      </div>
      {systemError && (
        <div className="ms-error" role="alert">{systemError}</div>
      )}
    </div>
  )
}
```

- [ ] **Step 4: Run component tests — all 15 must pass**

```
npm test -- tests/renderer/MachineStatusPanel.test.tsx --reporter=verbose
```

Expected: `15 passed (15)`

- [ ] **Step 5: Run full suite**

```
npm test -- --reporter=verbose
```

Expected: `89 passed (89)` (65 + 9 hook + 15 panel)

- [ ] **Step 6: Commit**

```
git add src/renderer/src/components/panels/MachineStatusPanel.tsx \
        tests/renderer/MachineStatusPanel.test.tsx
git commit -m "feat(desktop): add MachineStatusPanel with state badge, spindle, feed, homed, G-code"
```

---

## Task 4: Wire AppShell

**Files:**
- Modify: `desktop-client/src/renderer/src/components/AppShell.tsx`

Two edits: add import, update `components` map, update `handleAddPanel`.

The `AppShell.tsx` file currently starts with these imports:
```typescript
import { useEffect, useRef } from 'react'
import { DockviewReact } from 'dockview'
import type { DockviewApi, IDockviewPanelProps } from 'dockview'
import { TabBar } from './TabBar'
import { PanelPicker } from './PanelPicker'
import { PlaceholderPanel } from './panels/PlaceholderPanel'
import { useLayoutStore } from '../store/layout'
```

And the current `components` map and `handleAddPanel` are:
```typescript
const components = {
  placeholder: (props: IDockviewPanelProps<{ type: string }>) => (
    <PlaceholderPanel type={props.params.type} />
  ),
}
// ...
function handleAddPanel(panel: { type: string; title: string }): void {
    const api = dockviewApiRef.current
    if (!api) return
    api.addPanel({
      id: `${panel.type}-${Date.now()}`,
      component: 'placeholder',
      title: panel.title,
      params: { type: panel.type },
    })
  }
```

- [ ] **Step 1: Add the MachineStatusPanel import**

Add one line after the `PlaceholderPanel` import:

```typescript
import { MachineStatusPanel } from './panels/MachineStatusPanel'
```

- [ ] **Step 2: Update the components map**

Replace:
```typescript
const components = {
  placeholder: (props: IDockviewPanelProps<{ type: string }>) => (
    <PlaceholderPanel type={props.params.type} />
  ),
}
```

With:
```typescript
const components = {
  placeholder: (props: IDockviewPanelProps<{ type: string }>) => (
    <PlaceholderPanel type={props.params.type} />
  ),
  'machine-status': (_props: IDockviewPanelProps<{ type: string }>) => (
    <MachineStatusPanel />
  ),
}
```

- [ ] **Step 3: Update handleAddPanel to route by type**

Replace:
```typescript
function handleAddPanel(panel: { type: string; title: string }): void {
    const api = dockviewApiRef.current
    if (!api) return
    api.addPanel({
      id: `${panel.type}-${Date.now()}`,
      component: 'placeholder',
      title: panel.title,
      params: { type: panel.type },
    })
  }
```

With:
```typescript
function handleAddPanel(panel: { type: string; title: string }): void {
    const api = dockviewApiRef.current
    if (!api) return
    const component = panel.type === 'machine-status' ? 'machine-status' : 'placeholder'
    api.addPanel({
      id: `${panel.type}-${Date.now()}`,
      component,
      title: panel.title,
      params: { type: panel.type },
    })
  }
```

- [ ] **Step 4: Run full suite**

```
npm test -- --reporter=verbose
```

Expected: `89 passed (89)` — existing AppShell tests mock dockview's `addPanel` and don't exercise the component routing, so no new tests are needed here.

- [ ] **Step 5: Commit**

```
git add src/renderer/src/components/AppShell.tsx
git commit -m "feat(desktop): wire machine-status panel into AppShell dockview component map"
```

---

## Task 5: Add CSS for Machine Status panel

**Files:**
- Modify: `desktop-client/src/renderer/src/App.css`

- [ ] **Step 1: Append panel CSS to App.css**

Open `App.css` and add these lines at the very end of the file:

```css
/* ── Machine Status Panel ── */
.machine-status-panel { display: flex; flex-direction: column; gap: 0.6rem; padding: 1rem; height: 100%; background: var(--bg-1); overflow: auto; }
.ms-header { display: flex; align-items: center; justify-content: space-between; }
.ms-state-badge { font-size: 1.1rem; font-weight: 700; letter-spacing: 0.05em; transition: opacity 0.3s; }
.ms-backend { font-size: 10px; color: var(--text-dim); border: 1px solid var(--border); border-radius: var(--radius); padding: 0.1rem 0.4rem; }
.ms-row { display: flex; gap: 1rem; font-size: 13px; }
.ms-label { color: var(--text-dim); min-width: 60px; }
.ms-error { background: rgba(255,68,68,0.15); border: 1px solid var(--danger); border-radius: var(--radius); padding: 0.5rem 0.75rem; color: var(--danger); font-size: 12px; margin-top: 0.5rem; }
```

CSS variables used (`--bg-1`, `--text-dim`, `--border`, `--radius`, `--danger`) are all defined in `:root` at the top of `App.css`. No new variables needed.

- [ ] **Step 2: Run full suite**

```
npm test -- --reporter=verbose
```

Expected: `89 passed (89)` — `vitest.config.ts` has `css: false`, so CSS changes don't affect tests.

- [ ] **Step 3: Commit**

```
git add src/renderer/src/App.css
git commit -m "style(desktop): add Machine Status panel CSS"
```

---

## Task 6: TypeScript check + build

**Files:** none (verification only)

- [ ] **Step 1: TypeScript strict check**

```
npx tsc --noEmit
```

Expected: no errors. If you see errors about `MachineStatus` fields that no longer exist (`tool`, `feed`, `units`, `spindle.state`, `backend`), find where they're referenced and remove or update them.

- [ ] **Step 2: Full production build**

```
npm run build
```

Expected: clean build — `out/main/index.js`, `out/preload/index.js`, `out/renderer/index.html` produced with no TypeScript or Vite errors.

- [ ] **Step 3: Manual smoke test (dev mode)**

```
npm run dev
```

Steps to verify:
1. App opens — log in with your Odoo credentials.
2. Open PanelPicker → add "Machine Status" panel.
3. Verify panel shows: IDLE state in green, spindle OFF, feed rate, homed axes, G-code line.
4. Values update every 2 seconds (watch the feed rate or active_gcode change if backend is live).
5. Minimize the Electron window. Wait 6 seconds. Restore. Verify immediate refresh (data is fresh, not 2s stale).
6. Stop the backend Docker service (`docker compose stop linuxcnc-bridge`). After 2 failed polls, panel should show stale indicator. Restart service — stale clears on next success.
7. Switch to a different workspace tab. Switch back. Verify only ONE interval is running (open DevTools → Console, no error stacks; or add temporary `console.log` to `fetchStatus` and confirm call rate).

- [ ] **Step 4: Commit final build confirmation**

No build artifact commits. Just ensure the commit log is clean:

```
git log --oneline -6
```

Expected to see:
```
style(desktop): add Machine Status panel CSS
feat(desktop): wire machine-status panel into AppShell dockview component map
feat(desktop): add MachineStatusPanel with state badge, spindle, feed, homed, G-code
feat(desktop): add useMachineStatus polling hook with visibility/focus pausing
fix(types): align MachineStatus with real bridge API response
```

---

## Self-Review

**1. Spec coverage:**

| Spec requirement | Task that covers it |
|---|---|
| Replace `MachineStatus` type with real shape | Task 1 |
| `useMachineStatus` hook, immediate fetch on mount | Task 2, test 1 |
| 2-second interval | Task 2, test 2 |
| Stale after 2 failures | Task 2, test 3 |
| Stale clears on success | Task 2, test 4 |
| Pause on hidden | Task 2, test 5 |
| Immediate fetch on resume (visible) | Task 2, test 6 |
| No fetch after unmount | Task 2, test 7 |
| No interval accumulation (Gotcha 2) | Task 2, test 8 |
| Pause/resume on blur/focus | Task 2, test 9 |
| Loading placeholders | Task 3, test 1 |
| State badge with per-state color | Task 3, tests 2-4 |
| Spindle off / on display | Task 3, tests 5-6 |
| Feed rate, homed, G-code | Task 3, tests 7-10 |
| System error banner | Task 3, test 11 |
| No banner without error | Task 3, test 12 |
| Stale visual indicator | Task 3, test 13 |
| Fetch error with no data | Task 3, test 14 |
| Partial data → no crash (Gotcha 3) | Task 3, test 15 |
| Panel has zero polling code (Gotcha 1) | Task 3 implementation + spec reviewer check |
| AppShell wiring | Task 4 |
| CSS | Task 5 |
| TypeScript + build clean | Task 6 |

All spec requirements covered. ✅

**2. Placeholder scan:** No TBD/TODO/placeholder text anywhere in the plan. All steps contain complete code. ✅

**3. Type consistency:**
- `UseMachineStatusResult` — defined in hook (Task 2), imported by panel test (Task 3) ✅
- `MachineStatus` — defined in Task 1, used as `result as MachineStatus` in hook (Task 2), used in test fixtures as `idleStatus` (Task 3) ✅
- `useMachineStatus()` — function name consistent in hook file, panel, and tests ✅
- `MachineStatusPanel` — named export consistent in component file, AppShell import, and test import ✅
- `makeResult` helper in panel tests — consistent with `UseMachineStatusResult` fields ✅
