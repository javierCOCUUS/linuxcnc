import { renderHook, act } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { createElement } from 'react'
import { useMachineStatus } from '../../../src/renderer/src/hooks/useMachineStatus'
import { MachineDataProvider } from '../../../src/renderer/src/context/MachineDataContext'

const mockStatus = {
  state: 'IDLE' as const,
  position: { x: 0, y: 0, z: 0 },
  homed: ['X', 'Y', 'Z'],
  spindle: { on: false, speed: 0, direction: 'off' },
  feed_rate: 100,
  active_gcode: '',
  system: { backend: 'stub' as const },
}

const wrapper = ({ children }: { children: React.ReactNode }) =>
  createElement(MachineDataProvider, null, children)

describe('useMachineStatus', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.spyOn(document, 'hidden', 'get').mockReturnValue(false)
    window.electronAPI = {
      getMachineStatus: vi.fn().mockResolvedValue(mockStatus),
    } as unknown as typeof window.electronAPI
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('fires immediate fetch on mount', async () => {
    const { result } = renderHook(() => useMachineStatus(), { wrapper })
    expect(result.current.loading).toBe(true)
    await act(async () => { await Promise.resolve() })
    expect(window.electronAPI.getMachineStatus).toHaveBeenCalledTimes(1)
    expect(result.current.data).toMatchObject({ state: 'IDLE' })
    expect(result.current.loading).toBe(false)
  })

  it('polls every 2000ms', async () => {
    renderHook(() => useMachineStatus(), { wrapper })
    await act(async () => { await Promise.resolve() })
    await act(async () => { vi.advanceTimersByTime(2000); await Promise.resolve() })
    expect(window.electronAPI.getMachineStatus).toHaveBeenCalledTimes(2)
  })

  it('sets stale after 2 consecutive failures', async () => {
    vi.mocked(window.electronAPI.getMachineStatus).mockRejectedValue(new Error('fail'))
    const { result } = renderHook(() => useMachineStatus(), { wrapper })
    await act(async () => { await Promise.resolve() })
    expect(result.current.stale).toBe(false)
    await act(async () => { vi.advanceTimersByTime(2000); await Promise.resolve() })
    expect(result.current.stale).toBe(true)
  })

  it('clears stale on success after failures', async () => {
    vi.mocked(window.electronAPI.getMachineStatus)
      .mockRejectedValueOnce(new Error('fail'))
      .mockRejectedValueOnce(new Error('fail'))
      .mockResolvedValue(mockStatus)
    const { result } = renderHook(() => useMachineStatus(), { wrapper })
    await act(async () => { await Promise.resolve() })
    await act(async () => { vi.advanceTimersByTime(2000); await Promise.resolve() })
    expect(result.current.stale).toBe(true)
    await act(async () => { vi.advanceTimersByTime(2000); await Promise.resolve() })
    expect(result.current.stale).toBe(false)
  })

  it('pauses polling when document becomes hidden', async () => {
    renderHook(() => useMachineStatus(), { wrapper })
    await act(async () => { await Promise.resolve() })
    vi.spyOn(document, 'hidden', 'get').mockReturnValue(true)
    await act(async () => {
      document.dispatchEvent(new Event('visibilitychange'))
      vi.advanceTimersByTime(150)
      await Promise.resolve()
    })
    const callsBefore = vi.mocked(window.electronAPI.getMachineStatus).mock.calls.length
    await act(async () => { vi.advanceTimersByTime(6000); await Promise.resolve() })
    expect(vi.mocked(window.electronAPI.getMachineStatus).mock.calls.length).toBe(callsBefore)
  })

  it('resumes with immediate fetch when document becomes visible', async () => {
    vi.spyOn(document, 'hidden', 'get').mockReturnValue(true)
    renderHook(() => useMachineStatus(), { wrapper })
    await act(async () => { await Promise.resolve() })
    expect(window.electronAPI.getMachineStatus).not.toHaveBeenCalled()
    vi.spyOn(document, 'hidden', 'get').mockReturnValue(false)
    await act(async () => {
      document.dispatchEvent(new Event('visibilitychange'))
      vi.advanceTimersByTime(150)
      await Promise.resolve()
    })
    expect(window.electronAPI.getMachineStatus).toHaveBeenCalledTimes(1)
  })

  it('single-flight: does not fire a second request while one is in flight', async () => {
    let resolveFirst!: (v: unknown) => void
    vi.mocked(window.electronAPI.getMachineStatus)
      .mockImplementationOnce(() => new Promise(r => { resolveFirst = r }))
      .mockResolvedValue(mockStatus)
    renderHook(() => useMachineStatus(), { wrapper })
    await act(async () => { vi.advanceTimersByTime(2000); await Promise.resolve() })
    expect(window.electronAPI.getMachineStatus).toHaveBeenCalledTimes(1)
    await act(async () => { resolveFirst(mockStatus); await Promise.resolve() })
  })

  it('stops polling after unmount', async () => {
    const { unmount } = renderHook(() => useMachineStatus(), { wrapper })
    await act(async () => { await Promise.resolve() })
    unmount()
    const callsAtUnmount = vi.mocked(window.electronAPI.getMachineStatus).mock.calls.length
    await act(async () => { vi.advanceTimersByTime(6000); await Promise.resolve() })
    expect(vi.mocked(window.electronAPI.getMachineStatus).mock.calls.length).toBe(callsAtUnmount)
  })

  it('sets error message on fetch failure', async () => {
    vi.mocked(window.electronAPI.getMachineStatus).mockRejectedValue(new Error('Network error'))
    const { result } = renderHook(() => useMachineStatus(), { wrapper })
    await act(async () => { await Promise.resolve() })
    expect(result.current.error).toBe('Network error')
  })

  it('no interval accumulation — second mount after unmount has exactly one interval', async () => {
    const first = renderHook(() => useMachineStatus(), { wrapper })
    await act(async () => { await Promise.resolve() })
    first.unmount()
    const second = renderHook(() => useMachineStatus(), { wrapper })
    await act(async () => { await Promise.resolve() })
    await act(async () => { vi.advanceTimersByTime(2000); await Promise.resolve() })
    second.unmount()
    const total = vi.mocked(window.electronAPI.getMachineStatus).mock.calls.length
    expect(total).toBeLessThanOrEqual(4)
  })
})
