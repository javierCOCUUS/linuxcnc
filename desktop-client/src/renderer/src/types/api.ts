export interface MachineStatus {
  state: 'IDLE' | 'RUN' | 'PAUSED' | 'ESTOP' | 'UNAVAILABLE'
  backend: 'stub' | 'linuxcncrsh'
  position: { x: number; y: number; z: number }
  spindle: { speed: number; state: string }
  tool: number
  feed: number
  units: string
  error?: string
}

export interface WorkspaceFile {
  name: string
  size: number
  modified: number
}
