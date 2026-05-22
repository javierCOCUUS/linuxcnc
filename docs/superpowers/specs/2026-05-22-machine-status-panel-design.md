# Machine Status Panel — Design Spec

> **For agentic workers:** Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement from the corresponding plan. Do NOT change backend, CNC control logic, or any file outside `desktop-client/`.

**Goal:** Replace the `machine-status` placeholder panel with a real read-only panel that polls `electronAPI.getMachineStatus()` every 2 seconds and displays machine state, spindle, feed rate, homed axes, active G-code, and errors.

**Architecture:** Custom hook (`useMachineStatus`) owns polling logic; thin panel component (`MachineStatusPanel`) renders what the hook returns. AppShell routes dockview component type `'machine-status'` to the new panel. All other panel types remain as `PlaceholderPanel`.

**Tech stack:** React 18 + TypeScript 5.4 + Electron IPC + Vitest + @testing-library/react. No new dependencies.

---

## 1. Type Correction — `api.ts`

The existing `MachineStatus` interface was written speculatively and does not match the actual bridge response. Replace it entirely:

```typescript
// desktop-client/src/renderer/src/types/api.ts

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

**Removed fields:** `backend` (now lives in `system.backend`), `tool`, `feed` (renamed `feed_rate`), `units`, `spindle.state` (split into `spindle.on` + `spindle.direction`).

The `MachineStatus` type is only used by the `getMachineStatus()` IPC call and `machine:status` IPC handler — no other code references the removed fields.

---

## 2. `useMachineStatus` Hook

**File:** `desktop-client/src/renderer/src/hooks/useMachineStatus.ts`

**Return type:**
```typescript
interface UseMachineStatusResult {
  data: MachineStatus | null
  error: string | null
  stale: boolean
  loading: boolean
}
```

**Polling behavior:**
- Poll `window.electronAPI.getMachineStatus()` every **2000 ms**.
- On mount: check `document.hidden && !document.hasFocus()`. If visible and focused, fire an **immediate fetch** (no waiting for first interval tick), then start the 2-second interval. If already hidden on mount, skip fetch and wait for the visibility/focus events.
- **Pause when hidden/blurred:** listen to `document.visibilitychange` and `window.blur`. When `document.hidden` or not focused, clear the interval.
- **Resume with immediate fetch:** on `document.visibilitychange` (visible) or `window.focus`, fire an immediate fetch, then restart the interval. The user sees fresh data the moment they switch back to the app.
- **Stale detection:** increment a consecutive-failure counter on each fetch error. When counter reaches **2**, set `stale: true`. Reset counter and `stale` to 0/false on any successful fetch.
- **Error field:** set to the caught error message on failure; set to `null` on success.
- **Loading:** `true` only until the first fetch completes (success or failure).
- **Cleanup:** clear interval + remove all event listeners on unmount.

**No side effects outside the hook** — it does not write to any store, does not call any IPC other than `getMachineStatus`.

---

## 3. `MachineStatusPanel` Component

**File:** `desktop-client/src/renderer/src/components/panels/MachineStatusPanel.tsx`

Calls `useMachineStatus()`, renders a read-only status display. No props needed — the hook owns the data.

### Layout (top to bottom)

```
┌──────────────────────────────────┐
│  ● IDLE          [stub]          │  ← state badge + backend chip
│  ⚙ OFF                           │  ← spindle
│  ⟶ Feed 100%                     │  ← feed_rate
│  Homed: X Y Z                    │  ← homed axes
│  G54 G17 G90                     │  ← active_gcode
│                                  │
│  ┌──── ERROR ───────────────┐    │  ← only when system.error is set
│  │ <error text>             │    │
│  └──────────────────────────┘    │
└──────────────────────────────────┘
```

**State badge colors:**
| state | color |
|---|---|
| `IDLE` | green (`#22c55e`) |
| `RUN` | blue (`#00aaff` — matches `--accent`) |
| `PAUSED` | amber (`#f59e0b`) |
| `MDI` | purple (`#a855f7`) |
| `ESTOP` | red (`#ff4444` — matches `--danger`) |
| `UNAVAILABLE` | gray (`#666` — matches `--text-dim`) |

**Stale modifier:** when `stale: true`, reduce badge opacity to 0.5 and append `(stale)` to the state text.

**Loading state:** when `loading: true` (no data yet), show `—` placeholders for all fields.

**Error banner:** shown only when `data?.system?.error` is a non-empty string. Red background block under the main fields.

### CSS

Add panel-specific CSS to `App.css` under a `/* ── Machine Status Panel ── */` comment block. Follow existing naming conventions (`machine-status-panel`, `ms-state-badge`, `ms-row`, etc.).

---

## 4. AppShell Wiring

**File:** `desktop-client/src/renderer/src/components/AppShell.tsx`

Current `components` map:
```typescript
const components = {
  placeholder: (props) => <PlaceholderPanel type={props.params.type} />,
}
```

New `components` map:
```typescript
const components = {
  placeholder: (props) => <PlaceholderPanel type={props.params.type} />,
  'machine-status': (_props) => <MachineStatusPanel />,
}
```

`handleAddPanel` currently hardcodes `component: 'placeholder'`. Change it to route by type:

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

No other changes to AppShell.

---

## 5. Tests

### `tests/renderer/hooks/useMachineStatus.test.ts`
- Uses `vi.useFakeTimers()` + mocked `window.electronAPI.getMachineStatus`
- **Immediate fetch on mount** — first fetch fires without advancing timers
- **Interval polling** — after advancing 2000 ms, a second fetch fires
- **Stale after 2 consecutive failures** — mock rejects twice; verify `stale: true` on second failure
- **Stale clears on success** — after stale, mock resolves; verify `stale: false`
- **Pause on hidden** — set `document.hidden = true`, fire `visibilitychange`; advance timers; verify no additional fetch
- **Immediate fetch on resume** — after hidden, set `document.hidden = false`, fire `visibilitychange`; verify fetch fires immediately
- **Cleanup** — unmount; advance timers; verify no fetch fires after unmount

### `tests/renderer/MachineStatusPanel.test.tsx`
- **Loading state** — before first fetch resolves, shows `—` placeholders
- **IDLE state** — renders green state badge, spindle off, feed rate, homed axes, active G-code
- **RUN state** — badge is blue, spindle shows on + rpm + direction
- **ESTOP state** — badge is red
- **UNAVAILABLE + error** — badge is gray, error banner visible with error text
- **Stale state** — badge at reduced opacity, `(stale)` text appended
- **Error (fetch failure, no data)** — shows error message

---

## 6. File Summary

| File | Action |
|---|---|
| `src/renderer/src/types/api.ts` | Modify — replace `MachineStatus` type |
| `src/renderer/src/hooks/useMachineStatus.ts` | Create |
| `src/renderer/src/components/panels/MachineStatusPanel.tsx` | Create |
| `src/renderer/src/components/AppShell.tsx` | Modify — add component + route by type |
| `src/renderer/src/App.css` | Modify — add panel CSS |
| `tests/renderer/hooks/useMachineStatus.test.ts` | Create |
| `tests/renderer/MachineStatusPanel.test.tsx` | Create |

**Not touched:** `ipc-handlers.ts`, `preload/index.ts`, `electron-api.d.ts`, all backend files, all other panels.

---

## 7. Constraints

- Do NOT change backend, CNC control logic, Docker, or any file outside `desktop-client/`.
- Do NOT add polling to any panel other than `machine-status` in this task.
- Do NOT add machine control buttons — this panel is read-only.
- All 65 existing tests must continue to pass.
- The panel must not crash when the backend is unreachable (show error state gracefully).
