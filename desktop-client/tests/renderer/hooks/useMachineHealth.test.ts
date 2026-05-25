import { renderHook, act } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useMachineHealth } from '../../../src/renderer/src/hooks/useMachineHealth'

const mockHealth = {
  backend: 'linuxcncrsh' as const,
  status: 'ok' as const,
  linuxcncrsh: { status: 'ok' as const, latency_ms: 12 },
  hal_bridge:  { status: 'ok' as const, latency_ms: 8 },
  mesa_pins:   { status: 'ok' as const, latency_ms: 25, count: 47 },
}

beforeEach(() => {
  vi.useFakeTimers()
  vi.spyOn(document, 'hidden', 'get').mockReturnValue(false)
  window.electronAPI = {
    getMachineHealth: vi.fn().mockResolvedValue(mockHealth),
  } as unknown as typeof window.electronAPI
})

afterEach(() => {
  vi.useRealTimers()
  vi.restoreAllMocks()
})

describe('useMachineHealth', () => {
  it('starts loading, resolves on mount', async () => {
    const { result } = renderHook(() => useMachineHealth())
    expect(result.current.loading).toBe(true)
    await act(async () => { await Promise.resolve() })
    expect(result.current.loading).toBe(false)
    expect(result.current.data).toMatchObject({ status: 'ok' })
  })

  it('polls every 10 000ms', async () => {
    renderHook(() => useMachineHealth())
    await act(async () => { await Promise.resolve() })
    await act(async () => { vi.advanceTimersByTime(10_000); await Promise.resolve() })
    expect(window.electronAPI.getMachineHealth).toHaveBeenCalledTimes(2)
  })

  it('does NOT call getMachineStatus', async () => {
    const spy = vi.fn()
    window.electronAPI = {
      ...window.electronAPI,
      getMachineStatus: spy,
    } as unknown as typeof window.electronAPI
    renderHook(() => useMachineHealth())
    await act(async () => { await Promise.resolve() })
    expect(spy).not.toHaveBeenCalled()
  })

  it('sets error on failure', async () => {
    vi.mocked(window.electronAPI.getMachineHealth).mockRejectedValue(new Error('timeout'))
    const { result } = renderHook(() => useMachineHealth())
    await act(async () => { await Promise.resolve() })
    expect(result.current.error).toBe('timeout')
  })

  it('clears error on subsequent success', async () => {
    vi.mocked(window.electronAPI.getMachineHealth)
      .mockRejectedValueOnce(new Error('down'))
      .mockResolvedValue(mockHealth)
    const { result } = renderHook(() => useMachineHealth())
    await act(async () => { await Promise.resolve() })
    expect(result.current.error).toBe('down')
    await act(async () => { vi.advanceTimersByTime(10_000); await Promise.resolve() })
    expect(result.current.error).toBeNull()
    expect(result.current.data).toMatchObject({ status: 'ok' })
  })

  it('stops polling after unmount', async () => {
    const { unmount } = renderHook(() => useMachineHealth())
    await act(async () => { await Promise.resolve() })
    unmount()
    const calls = vi.mocked(window.electronAPI.getMachineHealth).mock.calls.length
    await act(async () => { vi.advanceTimersByTime(30_000); await Promise.resolve() })
    expect(vi.mocked(window.electronAPI.getMachineHealth).mock.calls.length).toBe(calls)
  })

  it('pauses when document hidden', async () => {
    renderHook(() => useMachineHealth())
    await act(async () => { await Promise.resolve() })
    vi.spyOn(document, 'hidden', 'get').mockReturnValue(true)
    await act(async () => {
      document.dispatchEvent(new Event('visibilitychange'))
      vi.advanceTimersByTime(150)
      await Promise.resolve()
    })
    const callsBefore = vi.mocked(window.electronAPI.getMachineHealth).mock.calls.length
    await act(async () => { vi.advanceTimersByTime(30_000); await Promise.resolve() })
    expect(vi.mocked(window.electronAPI.getMachineHealth).mock.calls.length).toBe(callsBefore)
  })

  it('resumes with immediate fetch when visible again', async () => {
    vi.spyOn(document, 'hidden', 'get').mockReturnValue(true)
    renderHook(() => useMachineHealth())
    await act(async () => { await Promise.resolve() })
    expect(window.electronAPI.getMachineHealth).not.toHaveBeenCalled()
    vi.spyOn(document, 'hidden', 'get').mockReturnValue(false)
    await act(async () => {
      document.dispatchEvent(new Event('visibilitychange'))
      vi.advanceTimersByTime(150)
      await Promise.resolve()
    })
    expect(window.electronAPI.getMachineHealth).toHaveBeenCalledTimes(1)
  })
})
