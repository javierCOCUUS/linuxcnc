export interface MachineStatus {
  state: 'IDLE' | 'RUNNING' | 'OFF' | 'PAUSED' | 'ESTOP' | 'UNAVAILABLE' | 'MDI'
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
