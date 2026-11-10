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
  importMultipleConnections: (
    inputs: unknown[],
    extraGroups?: string[]
  ): Promise<{ imported: number; failed: number }> => {
    const safeInputs = JSON.parse(JSON.stringify(inputs || []))
    const safeGroups = extraGroups ? JSON.parse(JSON.stringify(extraGroups)) : []
    return ipcRenderer.invoke('connections:import-multiple', safeInputs, safeGroups)
  },
  openFileDialog: (options?: {
    title?: string
    filters?: { name: string; extensions: string[] }[]
  }): Promise<{ canceled: boolean; filePath?: string; content?: string; error?: string }> =>
    ipcRenderer.invoke('dialog:open-file', options),
  saveFileDialog: (options: {
    title?: string
    defaultPath?: string
    content: string
    filters?: { name: string; extensions: string[] }[]
  }): Promise<{ canceled: boolean; filePath?: string; error?: string }> =>
    ipcRenderer.invoke('dialog:save-file', options),
  detectDBeaver: (): Promise<{
    found: boolean
    path?: string
    content?: string
    credentials?: Record<string, any>
  }> => ipcRenderer.invoke('tools:detect-dbeaver'),
  extractDBeaverDbp: (
    filePath: string
  ): Promise<{
    success: boolean
    content?: string
    credentials?: Record<string, any>
    error?: string
  }> => ipcRenderer.invoke('tools:extract-dbeaver-dbp', filePath),
  decryptDBeaverCredentials: (byteArr: number[]): Promise<Record<string, any>> =>
    ipcRenderer.invoke('tools:decrypt-dbeaver-credentials', byteArr),
  getGroups: (): Promise<string[]> => ipcRenderer.invoke('groups:get-all'),
  addGroup: (name: string): Promise<string> => ipcRenderer.invoke('groups:add', name),
  renameGroup: (oldName: string, newName: string): Promise<boolean> =>
    ipcRenderer.invoke('groups:rename', oldName, newName),
  deleteGroup: (name: string): Promise<boolean> => ipcRenderer.invoke('groups:delete', name),
  // SFTP & Local Filesystem APIs
  sftpConnect: (config: {
    sessionId?: string
    host: string
    port: number
    user: string
    password?: string
    timeoutMs?: number
    skipCwd?: boolean
  }): Promise<{ success: boolean; message: string; cwd?: string }> =>
    ipcRenderer.invoke('sftp:connect', config),
  sftpDisconnect: (sessionId?: string): Promise<void> =>
    ipcRenderer.invoke('sftp:disconnect', sessionId),
  sftpGetStatus: (sessionId?: string): Promise<boolean> =>
    ipcRenderer.invoke('sftp:status', sessionId),
  sshExec: (
    command: string,
    sessionId?: string,
    asSudo?: boolean
  ): Promise<{ stdout: string; stderr: string; code: number }> =>
    ipcRenderer.invoke('ssh:exec', { command, sessionId, asSudo }),
  sftpListRemote: (remotePath: string, sessionId?: string): Promise<any[]> =>
    ipcRenderer.invoke('sftp:list-remote', { remotePath, sessionId }),
  sftpUpload: (localPath: string, remotePath: string, sessionId?: string, asSudo?: boolean): Promise<void> =>
    ipcRenderer.invoke('sftp:upload', { localPath, remotePath, sessionId, asSudo }),
  sftpDownload: (remotePath: string, localPath: string, sessionId?: string, asSudo?: boolean): Promise<void> =>
    ipcRenderer.invoke('sftp:download', { remotePath, localPath, sessionId, asSudo }),
  sftpMkdirRemote: (remotePath: string, sessionId?: string, asSudo?: boolean): Promise<void> =>
    ipcRenderer.invoke('sftp:mkdir-remote', { remotePath, sessionId, asSudo }),
  sftpDeleteRemote: (
    remotePath: string,
    isDirectory?: boolean,
    sessionId?: string,
    asSudo?: boolean
  ): Promise<void> =>
    ipcRenderer.invoke('sftp:delete-remote', { remotePath, isDirectory, sessionId, asSudo }),
  sftpRenameRemote: (
    oldPath: string,
    newPath: string,
    sessionId?: string,
    asSudo?: boolean
  ): Promise<void> =>
    ipcRenderer.invoke('sftp:rename-remote', { oldPath, newPath, sessionId, asSudo }),
  sftpChmodRemote: (
    remotePath: string,
    mode: string | number,
    sessionId?: string,
    asSudo?: boolean
  ): Promise<void> =>
    ipcRenderer.invoke('sftp:chmod-remote', { remotePath, mode, sessionId, asSudo }),
  sftpReadFile: (
    remotePath: string,
    sessionId?: string,
    asSudo?: boolean
  ): Promise<string> =>
    ipcRenderer.invoke('sftp:read-file', { remotePath, sessionId, asSudo }),
  sftpWriteFile: (
    remotePath: string,
    content: string,
    sessionId?: string,
    asSudo?: boolean
  ): Promise<void> =>
    ipcRenderer.invoke('sftp:write-file', { remotePath, content, sessionId, asSudo }),
  sftpGetGitInfo: (
    remotePath: string,
    sessionId?: string
  ): Promise<{ isGit: boolean; branch: string; isDirty: boolean }> =>
    ipcRenderer.invoke('sftp:get-git-info', { remotePath, sessionId }),
  sftpGetGitBlame: (
    filePath: string,
    line: number,
    sessionId?: string
  ): Promise<{ author: string; timeAgo: string; summary: string; hash: string; isUncommitted: boolean } | null> =>
    ipcRenderer.invoke('sftp:get-git-blame', { filePath, line, sessionId }),
  sftpGetGitStatus: (
    remotePath: string,
    sessionId?: string
  ): Promise<{
    isGit: boolean
    branch: string
    root: string
    files: { path: string; relPath: string; status: 'M' | 'A' | 'D' | 'U'; staged: boolean }[]
  }> =>
    ipcRenderer.invoke('sftp:get-git-status', { remotePath, sessionId }),
  sftpGitCommit: (
    remotePath: string,
    message: string,
    sessionId?: string
  ): Promise<{ success: boolean; message: string }> =>
    ipcRenderer.invoke('sftp:git-commit', { remotePath, message, sessionId }),
  sftpGitDiscard: (
    filePath: string,
    sessionId?: string
  ): Promise<void> =>
    ipcRenderer.invoke('sftp:git-discard', { filePath, sessionId }),
  sftpGitStage: (
    filePath: string,
    staged: boolean,
    sessionId?: string
  ): Promise<void> =>
    ipcRenderer.invoke('sftp:git-stage', { filePath, staged, sessionId }),
  sftpGitStageAll: (remotePath: string, sessionId?: string): Promise<void> =>
    ipcRenderer.invoke('sftp:git-stage-all', { remotePath, sessionId }),
  sftpGitDiscardAll: (remotePath: string, sessionId?: string): Promise<void> =>
    ipcRenderer.invoke('sftp:git-discard-all', { remotePath, sessionId }),
  sftpGitPull: (
    remotePath: string,
    sessionId?: string
  ): Promise<{ success: boolean; message: string }> =>
    ipcRenderer.invoke('sftp:git-pull', { remotePath, sessionId }),
  sftpGitPush: (
    remotePath: string,
    sessionId?: string
  ): Promise<{ success: boolean; message: string }> =>
    ipcRenderer.invoke('sftp:git-push', { remotePath, sessionId }),
  sftpGitLog: (
    remotePath: string,
    sessionId?: string
  ): Promise<string> =>
    ipcRenderer.invoke('sftp:git-log', { remotePath, sessionId }),
  sftpGitGraphCommits: (
    remotePath: string,
    sessionId?: string,
    limit?: number
  ): Promise<string> =>
    ipcRenderer.invoke('sftp:git-graph-commits', { remotePath, sessionId, limit }),
  sftpGitCommitDetails: (
    remotePath: string,
    hash: string,
    sessionId?: string
  ): Promise<string> =>
    ipcRenderer.invoke('sftp:git-commit-details', { remotePath, hash, sessionId }),
  sftpGitFileDiff: (
    remotePath: string,
    hash: string,
    filePath: string,
    sessionId?: string
  ): Promise<string> =>
    ipcRenderer.invoke('sftp:git-file-diff', { remotePath, hash, filePath, sessionId }),
  sftpSearchRemote: (
    query: string,
    rootPath: string,
    sessionId?: string,
    options?: { isCaseSensitive?: boolean; isWholeWord?: boolean; isRegex?: boolean }
  ): Promise<{ file: string; line: number; text: string }[]> =>
    ipcRenderer.invoke('sftp:search-remote', {
      query,
      rootPath,
      sessionId,
      isCaseSensitive: options?.isCaseSensitive,
      isWholeWord: options?.isWholeWord,
      isRegex: options?.isRegex
    }),
  sftpRenameLocal: (oldPath: string, newPath: string, asSudo?: boolean): Promise<void> =>
    ipcRenderer.invoke('sftp:rename-local', { oldPath, newPath, asSudo }),
  sftpOpenLocal: (filePath: string): Promise<void> =>
    ipcRenderer.invoke('sftp:open-local', filePath),
  sftpGetLocalHome: (): Promise<string> => ipcRenderer.invoke('sftp:get-local-home'),
  sftpListLocal: (dirPath: string): Promise<any[]> =>
    ipcRenderer.invoke('sftp:list-local', dirPath),
  sftpMkdirLocal: (dirPath: string, asSudo?: boolean): Promise<void> =>
    ipcRenderer.invoke('sftp:mkdir-local', { dirPath, asSudo }),
  sftpDeleteLocal: (filePath: string, asSudo?: boolean): Promise<void> =>
    ipcRenderer.invoke('sftp:delete-local', { filePath, asSudo }),
  showNotification: (payload: {
    title: string
    body: string
    silent?: boolean
    tag?: string
    issueId?: number
  }): Promise<void> => ipcRenderer.invoke('app:show-notification', payload),
  onNotificationClick: (
    callback: (payload: { tag?: string; issueId?: number }) => void
  ): (() => void) => {
    const listener = (
      _: Electron.IpcRendererEvent,
      payload: { tag?: string; issueId?: number }
    ): void => callback(payload)
    ipcRenderer.on('app:notification-clicked', listener)
    return () => ipcRenderer.removeListener('app:notification-clicked', listener)
  },
  callGeminiApi: (payload: {
    url: string
    headers?: Record<string, string>
    body: string
  }): Promise<{
    ok: boolean
    status: number
    statusText?: string
    data?: any
    error?: string
  }> => ipcRenderer.invoke('ai:call-gemini', payload),
  signInWithGoogle: (): Promise<{
    success: boolean
    token?: string
    refreshToken?: string
    email?: string
    error?: string
  }> => ipcRenderer.invoke('ai:google-sign-in'),
  refreshGoogleToken: (refreshToken: string): Promise<{
    success: boolean
    token?: string
    error?: string
  }> => ipcRenderer.invoke('ai:google-refresh-token', refreshToken),
  callRedmineApi: (payload: {
    url: string
    method?: string
    headers?: Record<string, string>
    body?: string
    bodyBase64?: string
    responseType?: 'json' | 'text' | 'dataUrl'
  }): Promise<{
    ok: boolean
    status: number
    statusText?: string
    data?: any
    error?: string
  }> => ipcRenderer.invoke('redmine:request', payload)
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
