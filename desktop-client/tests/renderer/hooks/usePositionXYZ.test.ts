import { renderHook, act } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest'
import { usePositionXYZ } from '../../../src/renderer/src/hooks/usePositionXYZ'

const mockStatus = {
  state: 'IDLE' as const,
  position: { x: 1.0, y: 2.0, z: 3.0 },
  homed: ['X', 'Y'],
  spindle: { on: false, speed: 0, direction: 'off' },
  feed_rate: 100,
  active_gcode: '',
  system: { backend: 'stub' as const },
}

describe('usePositionXYZ', () => {
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
    const { result } = renderHook(() => usePositionXYZ())
    expect(result.current.loading).toBe(true)
    await act(async () => { await Promise.resolve() })
    expect(window.electronAPI.getMachineStatus).toHaveBeenCalledTimes(1)
    expect(result.current.position).toEqual({ x: 1.0, y: 2.0, z: 3.0 })
    expect(result.current.loading).toBe(false)
  })

  it('polls every 2000ms', async () => {
    renderHook(() => usePositionXYZ())
    await act(async () => { await Promise.resolve() })
    await act(async () => { vi.advanceTimersByTime(2000); await Promise.resolve() })
    expect(window.electronAPI.getMachineStatus).toHaveBeenCalledTimes(2)
  })

  it('sets stale after 2 consecutive failures', async () => {
    vi.mocked(window.electronAPI.getMachineStatus).mockRejectedValue(new Error('fail'))
    const { result } = renderHook(() => usePositionXYZ())
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
    const { result } = renderHook(() => usePositionXYZ())
    await act(async () => { await Promise.resolve() })
    await act(async () => { vi.advanceTimersByTime(2000); await Promise.resolve() })
    expect(result.current.stale).toBe(true)
    await act(async () => { vi.advanceTimersByTime(2000); await Promise.resolve() })
    expect(result.current.stale).toBe(false)
  })

  it('pauses polling when document becomes hidden', async () => {
    renderHook(() => usePositionXYZ())
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
    renderHook(() => usePositionXYZ())
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

  it('stops polling after unmount', async () => {
    const { unmount } = renderHook(() => usePositionXYZ())
    await act(async () => { await Promise.resolve() })
    unmount()
    const callsAtUnmount = vi.mocked(window.electronAPI.getMachineStatus).mock.calls.length
    await act(async () => { vi.advanceTimersByTime(6000); await Promise.resolve() })
    expect(vi.mocked(window.electronAPI.getMachineStatus).mock.calls.length).toBe(callsAtUnmount)
  })

  it('returns homed axes from status response', async () => {
    const { result } = renderHook(() => usePositionXYZ())
    await act(async () => { await Promise.resolve() })
    expect(result.current.homed).toEqual(['X', 'Y'])
  })

  it('position {x:0,y:0,z:0} is valid — loading stays false and values are set', async () => {
    vi.mocked(window.electronAPI.getMachineStatus).mockResolvedValue({
      ...mockStatus,
      position: { x: 0, y: 0, z: 0 },
    })
    const { result } = renderHook(() => usePositionXYZ())
    await act(async () => { await Promise.resolve() })
    expect(result.current.loading).toBe(false)
    expect(result.current.position).toEqual({ x: 0, y: 0, z: 0 })
    expect(result.current.error).toBeNull()
  })
})
