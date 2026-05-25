import { useMachineData } from '../context/MachineDataContext'

export interface UsePositionXYZResult {
  position: { x: number; y: number; z: number } | null
  homed: string[]
  error: string | null
  stale: boolean
  loading: boolean
}

export function usePositionXYZ(): UsePositionXYZResult {
  const { data, error, stale, loading } = useMachineData()
  return {
    position: data?.position ?? null,
    homed:    data?.homed   ?? [],
    error,
    stale,
    loading,
  }
}
