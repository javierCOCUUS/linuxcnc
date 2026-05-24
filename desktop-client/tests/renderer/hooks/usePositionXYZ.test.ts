import { vi, describe, it, expect, beforeEach } from 'vitest'
import { renderHook } from '@testing-library/react'

vi.mock('../../../src/renderer/src/context/MachineDataContext', () => ({
  useMachineData: vi.fn(),
}))

import { usePositionXYZ } from '../../../src/renderer/src/hooks/usePositionXYZ'
import { useMachineData } from '../../../src/renderer/src/context/MachineDataContext'

const mockUseMachineData = vi.mocked(useMachineData)

const baseContext = {
  data: {
    state: 'IDLE' as const,
    position: { x: 1.0, y: 2.0, z: 3.0 },
    homed: ['X', 'Y'],
    spindle: { on: false, speed: 0, direction: 'off' },
    feed_rate: 100,
    active_gcode: '',
    system: { backend: 'stub' as const },
  },
  error: null,
  stale: false,
  loading: false,
}

beforeEach(() => {
  vi.clearAllMocks()
  mockUseMachineData.mockReturnValue(baseContext)
})

describe('usePositionXYZ', () => {
  it('returns position from context data', () => {
    const { result } = renderHook(() => usePositionXYZ())
    expect(result.current.position).toEqual({ x: 1.0, y: 2.0, z: 3.0 })
  })

  it('returns homed axes from context data', () => {
    const { result } = renderHook(() => usePositionXYZ())
    expect(result.current.homed).toEqual(['X', 'Y'])
  })

  it('returns null position when context has no data', () => {
    mockUseMachineData.mockReturnValue({ ...baseContext, data: null, loading: true })
    const { result } = renderHook(() => usePositionXYZ())
    expect(result.current.position).toBeNull()
    expect(result.current.homed).toEqual([])
  })

  it('propagates loading state from context', () => {
    mockUseMachineData.mockReturnValue({ ...baseContext, data: null, loading: true })
    const { result } = renderHook(() => usePositionXYZ())
    expect(result.current.loading).toBe(true)
  })

  it('propagates error from context', () => {
    mockUseMachineData.mockReturnValue({ ...baseContext, error: 'Connection refused' })
    const { result } = renderHook(() => usePositionXYZ())
    expect(result.current.error).toBe('Connection refused')
  })

  it('propagates stale state from context', () => {
    mockUseMachineData.mockReturnValue({ ...baseContext, stale: true })
    const { result } = renderHook(() => usePositionXYZ())
    expect(result.current.stale).toBe(true)
  })

  it('position {x:0,y:0,z:0} is valid — not treated as null', () => {
    mockUseMachineData.mockReturnValue({
      ...baseContext,
      data: { ...baseContext.data, position: { x: 0, y: 0, z: 0 } },
    })
    const { result } = renderHook(() => usePositionXYZ())
    expect(result.current.position).toEqual({ x: 0, y: 0, z: 0 })
    expect(result.current.loading).toBe(false)
  })

  it('does not call electronAPI.getMachineStatus directly', () => {
    const spy = vi.fn()
    window.electronAPI = { getMachineStatus: spy } as unknown as typeof window.electronAPI
    renderHook(() => usePositionXYZ())
    expect(spy).not.toHaveBeenCalled()
  })
})
