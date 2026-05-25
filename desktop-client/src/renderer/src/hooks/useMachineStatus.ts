import { useMachineData } from '../context/MachineDataContext'
import type { MachineStatus } from '../types/api'

export interface UseMachineStatusResult {
  data: MachineStatus | null
  error: string | null
  stale: boolean
  loading: boolean
}

export function useMachineStatus(): UseMachineStatusResult {
  return useMachineData()
}
