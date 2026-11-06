export interface HostItem {
  id: number
  name: string
  ip: string
  port: number
  remotePath: string
  branch: string
  status: string
  statusType: 'success' | 'warning' | 'error' | 'idle'
  group: string
  url?: string
  type?: string
  color?: string
  user?: string
  password?: string
  savePassword?: boolean
  database?: string
  notes?: string
  dbHost?: string
  dbPort?: number
  dbUser?: string
  dbPassword?: string
  dbSavePassword?: boolean
}

