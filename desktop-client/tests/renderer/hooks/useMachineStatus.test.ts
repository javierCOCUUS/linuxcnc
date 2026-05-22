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

beforeEach(() => {
  vi.useFakeTimers()
  hiddenSpy = vi.spyOn(document, 'hidden', 'get').mockReturnValue(false)
  mockAPI(() => Promise.resolve(mockStatus))
})

afterEach(() => {
  vi.useRealTimers()
  vi.clearAllMocks()
  hiddenSpy?.mockRestore()
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
