import { HostItem } from '../../types/connection'

export interface SshLogEntry {
  id: string
  text: string
  type: 'input' | 'output' | 'error' | 'system'
  timestamp: string
  dir?: string
  user?: string
  host?: string
  prompt?: string
}

export interface SshTab {
  id: string
  host: HostItem
  title: string
  status: 'connected' | 'connecting' | 'disconnected' | 'error'
  isExecuting?: boolean
  errorMessage?: string
  logs: SshLogEntry[]
  commandHistory: string[]
  currentDir: string
  latency?: number
  connectedAt?: string
}

