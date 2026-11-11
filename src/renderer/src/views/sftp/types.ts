export interface LogEntry {
  id: number
  type: 'status' | 'command' | 'response' | 'error'
  text: string
  time: string
}

export interface TransferItem {
  id: number
  name: string
  direction: 'upload' | 'download'
  source: string
  target: string
  size: number
  status: 'queued' | 'transferring' | 'completed' | 'failed'
  error?: string
  time: string
}

export interface SftpFileItem {
  name: string
  path: string
  isDirectory: boolean
  size: number
  modifyTime: number
  permissions?: string
  permissionsMode?: string
  author?: string
  owner?: string
  group?: string
  type: string
}

export interface LocalFileItem {
  name: string
  path: string
  isDirectory: boolean
  size: number
  modifyTime: number
  author?: string
}

export interface SftpTab {
  id: string
  sessionId: string
  hostId: number | null
  title: string
  host: string
  port: number
  user: string
  password?: string
  isConnected: boolean
  isConnecting: boolean
  statusText: string
  remotePath: string
  defaultRemotePath?: string
  remoteItems: SftpFileItem[]
  remoteLoading: boolean
  remoteSearch: string
  selectedRemoteFile: SftpFileItem | null
  logs: LogEntry[]
  transfers: TransferItem[]
}

export interface ContextMenuState {
  show: boolean
  x: number
  y: number
  target: 'local' | 'remote'
  item: any | null
}
