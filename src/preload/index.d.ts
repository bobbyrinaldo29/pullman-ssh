import { ElectronAPI } from '@electron-toolkit/preload'

declare global {
  interface Window {
    electron: ElectronAPI
    api: {
      platform: NodeJS.Platform
      minimizeWindow: () => void
      maximizeWindow: () => void
      closeWindow: () => void
      isWindowMaximized: () => Promise<boolean>
      onMaximizeChanged: (callback: (isMaximized: boolean) => void) => () => void
      getConnections: () => Promise<Record<string, unknown>[]>
      addConnection: (input: Record<string, unknown>) => Promise<Record<string, unknown>>
      updateConnection: (
        id: number,
        input: Record<string, unknown>
      ) => Promise<Record<string, unknown>>
      testConnection: (input: {
        type?: 'ssh' | 'database'
        host: string
        port: number
        user?: string
        password?: string
        database?: string
        timeoutMs?: number
        ssh?: {
          host: string
          port: number
          user: string
          password?: string
        }
      }) => Promise<{ success: boolean; message: string; latency?: number }>
      deleteConnection: (id: number) => Promise<boolean>
      getGroups: () => Promise<string[]>
      addGroup: (name: string) => Promise<string>
      renameGroup: (oldName: string, newName: string) => Promise<boolean>
      deleteGroup: (name: string) => Promise<boolean>
      sftpConnect: (config: {
        host: string
        port: number
        user: string
        password?: string
        timeoutMs?: number
      }) => Promise<{ success: boolean; message: string; cwd?: string }>
      sftpDisconnect: () => Promise<void>
      sftpGetStatus: () => Promise<boolean>
      sftpListRemote: (remotePath: string) => Promise<any[]>
      sftpUpload: (localPath: string, remotePath: string) => Promise<void>
      sftpDownload: (remotePath: string, localPath: string) => Promise<void>
      sftpMkdirRemote: (remotePath: string) => Promise<void>
      sftpDeleteRemote: (remotePath: string, isDirectory?: boolean) => Promise<void>
      sftpRenameRemote: (oldPath: string, newPath: string) => Promise<void>
      sftpGetLocalHome: () => Promise<string>
      sftpListLocal: (dirPath: string) => Promise<any[]>
      sftpMkdirLocal: (dirPath: string) => Promise<void>
      sftpDeleteLocal: (filePath: string) => Promise<void>
    }
  }
}
