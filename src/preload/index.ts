import { contextBridge, ipcRenderer } from 'electron'
import { electronAPI } from '@electron-toolkit/preload'

// Custom APIs for renderer
const api = {
  platform: process.platform,
  minimizeWindow: (): void => ipcRenderer.send('window-minimize'),
  maximizeWindow: (): void => ipcRenderer.send('window-maximize'),
  closeWindow: (): void => ipcRenderer.send('window-close'),
  isWindowMaximized: (): Promise<boolean> => ipcRenderer.invoke('window-is-maximized'),
  onMaximizeChanged: (callback: (isMaximized: boolean) => void): (() => void) => {
    const handler = (_: unknown, isMax: boolean): void => callback(isMax)
    ipcRenderer.on('window-maximize-changed', handler)
    return () => {
      ipcRenderer.removeListener('window-maximize-changed', handler)
    }
  },
  getConnections: (): Promise<unknown[]> => ipcRenderer.invoke('connections:get-all'),
  addConnection: (input: unknown): Promise<unknown> => ipcRenderer.invoke('connections:add', input),
  updateConnection: (id: number, input: unknown): Promise<unknown> =>
    ipcRenderer.invoke('connections:update', { id, input }),
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
  }): Promise<{ success: boolean; message: string; latency?: number }> =>
    ipcRenderer.invoke('connections:test', input),
  deleteConnection: (id: number): Promise<boolean> => ipcRenderer.invoke('connections:delete', id),
  getGroups: (): Promise<string[]> => ipcRenderer.invoke('groups:get-all'),
  addGroup: (name: string): Promise<string> => ipcRenderer.invoke('groups:add', name),
  renameGroup: (oldName: string, newName: string): Promise<boolean> =>
    ipcRenderer.invoke('groups:rename', oldName, newName),
  deleteGroup: (name: string): Promise<boolean> => ipcRenderer.invoke('groups:delete', name),
  // SFTP & Local Filesystem APIs
  sftpConnect: (config: {
    host: string
    port: number
    user: string
    password?: string
    timeoutMs?: number
  }): Promise<{ success: boolean; message: string; cwd?: string }> =>
    ipcRenderer.invoke('sftp:connect', config),
  sftpDisconnect: (): Promise<void> => ipcRenderer.invoke('sftp:disconnect'),
  sftpGetStatus: (): Promise<boolean> => ipcRenderer.invoke('sftp:status'),
  sftpListRemote: (remotePath: string): Promise<any[]> =>
    ipcRenderer.invoke('sftp:list-remote', remotePath),
  sftpUpload: (localPath: string, remotePath: string): Promise<void> =>
    ipcRenderer.invoke('sftp:upload', { localPath, remotePath }),
  sftpDownload: (remotePath: string, localPath: string): Promise<void> =>
    ipcRenderer.invoke('sftp:download', { remotePath, localPath }),
  sftpMkdirRemote: (remotePath: string): Promise<void> =>
    ipcRenderer.invoke('sftp:mkdir-remote', remotePath),
  sftpDeleteRemote: (remotePath: string, isDirectory?: boolean): Promise<void> =>
    ipcRenderer.invoke('sftp:delete-remote', { remotePath, isDirectory }),
  sftpRenameRemote: (oldPath: string, newPath: string): Promise<void> =>
    ipcRenderer.invoke('sftp:rename-remote', { oldPath, newPath }),
  sftpGetLocalHome: (): Promise<string> => ipcRenderer.invoke('sftp:get-local-home'),
  sftpListLocal: (dirPath: string): Promise<any[]> =>
    ipcRenderer.invoke('sftp:list-local', dirPath),
  sftpMkdirLocal: (dirPath: string): Promise<void> =>
    ipcRenderer.invoke('sftp:mkdir-local', dirPath),
  sftpDeleteLocal: (filePath: string): Promise<void> =>
    ipcRenderer.invoke('sftp:delete-local', filePath)
}

// Use `contextBridge` APIs to expose Electron APIs to
// renderer only if context isolation is enabled, otherwise
// just add to the DOM global.
if (process.contextIsolated) {
  try {
    contextBridge.exposeInMainWorld('electron', electronAPI)
    contextBridge.exposeInMainWorld('api', api)
  } catch (error) {
    console.error(error)
  }
} else {
  // @ts-ignore (define in dts)
  window.electron = electronAPI
  // @ts-ignore (define in dts)
  window.api = api
}
