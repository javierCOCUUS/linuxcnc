import { renderHook, act } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useHalInputs } from '../../../src/renderer/src/hooks/useHalInputs'

const P = 'hm2_7i95.0.inmux.00.'
const pins = [
  { name: `${P}input-08`, value: 'TRUE', raw: `  30 bit OUT TRUE ${P}input-08 ==> remote-estop0` },
]

beforeEach(() => {
  vi.useFakeTimers()
  vi.spyOn(document, 'hidden', 'get').mockReturnValue(false)
  window.electronAPI = {
    getHalInputs: vi.fn().mockResolvedValue(pins),
  } as unknown as typeof window.electronAPI
})

afterEach(() => {
  vi.useRealTimers()
  vi.restoreAllMocks()
})

describe('useHalInputs', () => {
  it('starts loading and resolves parsed inputs on mount', async () => {
    const { result } = renderHook(() => useHalInputs())
    expect(result.current.loading).toBe(true)
    await act(async () => { await Promise.resolve() })
    expect(result.current.loading).toBe(false)
    expect(result.current.inputs).toHaveLength(1)
    expect(result.current.inputs[0]).toMatchObject({ id: '08', on: true, signal: 'remote-estop0' })
  })

  it('polls every 500 ms', async () => {
    renderHook(() => useHalInputs())
    await act(async () => { await Promise.resolve() })
    await act(async () => { vi.advanceTimersByTime(500); await Promise.resolve() })
    expect(window.electronAPI.getHalInputs).toHaveBeenCalledTimes(2)
  })

  it('sets error on failure', async () => {
    vi.mocked(window.electronAPI.getHalInputs).mockRejectedValue(new Error('HTTP 403'))
    const { result } = renderHook(() => useHalInputs())
    await act(async () => { await Promise.resolve() })
    expect(result.current.error).toBe('HTTP 403')
    expect(result.current.loading).toBe(false)
  })

  it('keeps the last inputs and clears the error on a later success', async () => {
    vi.mocked(window.electronAPI.getHalInputs)
      .mockResolvedValueOnce(pins)
      .mockRejectedValueOnce(new Error('timeout'))
      .mockResolvedValue(pins)
    const { result } = renderHook(() => useHalInputs())
    await act(async () => { await Promise.resolve() })
    await act(async () => { vi.advanceTimersByTime(500); await Promise.resolve() })
    expect(result.current.error).toBe('timeout')
    expect(result.current.inputs).toHaveLength(1)
    await act(async () => { vi.advanceTimersByTime(500); await Promise.resolve() })
    expect(result.current.error).toBeNull()
  })

  it('does not poll while the window is hidden', async () => {
    vi.spyOn(document, 'hidden', 'get').mockReturnValue(true)
    renderHook(() => useHalInputs())
    await act(async () => { vi.advanceTimersByTime(2000); await Promise.resolve() })
    expect(window.electronAPI.getHalInputs).not.toHaveBeenCalled()
  })

  it('stops polling after unmount', async () => {
    const { unmount } = renderHook(() => useHalInputs())
    await act(async () => { await Promise.resolve() })
    unmount()
    const calls = vi.mocked(window.electronAPI.getHalInputs).mock.calls.length
    await act(async () => { vi.advanceTimersByTime(2000); await Promise.resolve() })
    expect(vi.mocked(window.electronAPI.getHalInputs).mock.calls.length).toBe(calls)
  })
})
