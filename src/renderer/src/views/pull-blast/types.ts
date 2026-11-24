import { HostItem } from '../../types/connection'

export type PullBlastStatus = 'idle' | 'connecting' | 'pulling' | 'success' | 'failed'

export interface ServerPullTask {
  host: HostItem
  selected: boolean
  remotePath: string
  branch: string
  status: PullBlastStatus
  durationMs?: number
  stdout: string
  stderr: string
  error?: string
  lastRunAt?: string
}

export interface PullBlastLogEntry {
  id: string
  timestamp: string
  hostId: number
  hostName: string
  type: 'info' | 'stdout' | 'stderr' | 'error' | 'success'
  message: string
}

export interface PullBlastConfig {
  branch: string
  remote: string
  autoStash: boolean
  runAsSudo: boolean
  checkoutBranch: boolean
  concurrency: number
}

export interface PullBlastSummary {
  total: number
  success: number
  failed: number
  running: number
  completed: number
  durationMs: number
}
