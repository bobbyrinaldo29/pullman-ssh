import { ElectronAPI } from '@electron-toolkit/preload'

declare global {
  interface Window {
    electron: ElectronAPI
    api: {
      platform: NodeJS.Platform
      setZoomFactor?: (factor: number) => void
      getZoomFactor?: () => number
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
      importMultipleConnections: (
        inputs: unknown[],
        extraGroups?: string[]
      ) => Promise<{ imported: number; failed: number }>
      openFileDialog: (options?: {
        title?: string
        filters?: { name: string; extensions: string[] }[]
      }) => Promise<{ canceled: boolean; filePath?: string; content?: string; error?: string }>
      saveFileDialog: (options: {
        title?: string
        defaultPath?: string
        content: string
        filters?: { name: string; extensions: string[] }[]
      }) => Promise<{ canceled: boolean; filePath?: string; error?: string }>
      detectDBeaver: () => Promise<{
        found: boolean
        path?: string
        content?: string
        credentials?: Record<string, any>
      }>
      extractDBeaverDbp: (
        filePath: string
      ) => Promise<{
        success: boolean
        content?: string
        credentials?: Record<string, any>
        error?: string
      }>
      decryptDBeaverCredentials: (byteArr: number[]) => Promise<Record<string, any>>
      getGroups: () => Promise<string[]>
      addGroup: (name: string) => Promise<string>
      renameGroup: (oldName: string, newName: string) => Promise<boolean>
      deleteGroup: (name: string) => Promise<boolean>
      sftpConnect: (config: {
        sessionId?: string
        host: string
        port: number
        user: string
        password?: string
        timeoutMs?: number
        skipCwd?: boolean
      }) => Promise<{ success: boolean; message: string; cwd?: string }>
      sftpDisconnect: (sessionId?: string) => Promise<void>
      sftpGetStatus: (sessionId?: string) => Promise<boolean>
      sshExec: (
        command: string,
        sessionId?: string,
        asSudo?: boolean
      ) => Promise<{ stdout: string; stderr: string; code: number }>
      sshShellStart: (
        sessionId: string,
        cols?: number,
        rows?: number,
        initialPath?: string
      ) => Promise<{ success: boolean; message?: string }>
      sshShellWrite: (sessionId: string, data: string) => void
      sshShellResize: (sessionId: string, cols: number, rows: number) => void
      sshShellClose: (sessionId: string) => Promise<{ success: boolean }>
      onSshShellData: (sessionId: string, callback: (data: string) => void) => () => void
      onSshShellClose: (sessionId: string, callback: () => void) => () => void
      sftpListRemote: (remotePath: string, sessionId?: string) => Promise<any[]>
      sftpUpload: (localPath: string, remotePath: string, sessionId?: string, asSudo?: boolean) => Promise<void>
      sftpDownload: (remotePath: string, localPath: string, sessionId?: string, asSudo?: boolean) => Promise<void>
      sftpMkdirRemote: (remotePath: string, sessionId?: string, asSudo?: boolean) => Promise<void>
      sftpDeleteRemote: (remotePath: string, isDirectory?: boolean, sessionId?: string, asSudo?: boolean) => Promise<void>
      sftpRenameRemote: (oldPath: string, newPath: string, sessionId?: string, asSudo?: boolean) => Promise<void>
      sftpChmodRemote: (remotePath: string, mode: string | number, sessionId?: string, asSudo?: boolean) => Promise<void>
      sftpReadFile: (remotePath: string, sessionId?: string, asSudo?: boolean) => Promise<string>
      sftpWriteFile: (remotePath: string, content: string, sessionId?: string, asSudo?: boolean) => Promise<void>
      sftpGetGitInfo: (remotePath: string, sessionId?: string) => Promise<{ isGit: boolean; branch: string; isDirty: boolean }>
      sftpGetGitBlame: (
        filePath: string,
        line: number,
        sessionId?: string
      ) => Promise<{ author: string; timeAgo: string; summary: string; hash: string; isUncommitted: boolean } | null>
      sftpGetGitStatus: (
        remotePath: string,
        sessionId?: string
      ) => Promise<{
        isGit: boolean
        branch: string
        root: string
        files: { path: string; relPath: string; status: 'M' | 'A' | 'D' | 'U'; staged: boolean }[]
      }>
      sftpGitCommit: (
        remotePath: string,
        message: string,
        sessionId?: string
      ) => Promise<{ success: boolean; message: string }>
      sftpGitDiscard: (
        filePath: string,
        sessionId?: string
      ) => Promise<void>
      sftpGitStage: (
        filePath: string,
        staged: boolean,
        sessionId?: string
      ) => Promise<void>
      sftpGitStageAll: (remotePath: string, sessionId?: string) => Promise<void>
      sftpGitDiscardAll: (remotePath: string, sessionId?: string) => Promise<void>
      sftpGitPull: (remotePath: string, sessionId?: string) => Promise<{ success: boolean; message: string }>
      sftpGitPush: (remotePath: string, sessionId?: string) => Promise<{ success: boolean; message: string }>
      sftpGitLog: (remotePath: string, sessionId?: string) => Promise<string>
      sftpGitGraphCommits: (remotePath: string, sessionId?: string, limit?: number) => Promise<string>
      sftpGitCommitDetails: (remotePath: string, hash: string, sessionId?: string) => Promise<string>
      sftpGitFileDiff: (
        remotePath: string,
        hash: string,
        filePath: string,
        sessionId?: string
      ) => Promise<{ diff: string; original: string; modified: string }>
      sftpSearchRemote: (
        query: string,
        rootPath: string,
        sessionId?: string,
        options?: { isCaseSensitive?: boolean; isWholeWord?: boolean; isRegex?: boolean }
      ) => Promise<{ file: string; line: number; text: string }[]>
      sftpRenameLocal: (oldPath: string, newPath: string, asSudo?: boolean) => Promise<void>
      sftpOpenLocal: (filePath: string) => Promise<void>
      sftpGetLocalHome: () => Promise<string>
      sftpListLocal: (dirPath: string) => Promise<any[]>
      sftpMkdirLocal: (dirPath: string, asSudo?: boolean) => Promise<void>
      sftpDeleteLocal: (filePath: string, asSudo?: boolean) => Promise<void>
      showNotification: (payload: {
        title: string
        subtitle?: string
        body: string
        silent?: boolean
        tag?: string
        issueId?: number
      }) => Promise<void>
      onNotificationClick: (
        callback: (payload: { tag?: string; issueId?: number }) => void
      ) => () => void
      callGeminiApi: (payload: {
        url: string
        headers?: Record<string, string>
        body: string
      }) => Promise<{
        ok: boolean
        status: number
        statusText?: string
        data?: any
        error?: string
      }>
      signInWithGoogle: () => Promise<{
        success: boolean
        token?: string
        refreshToken?: string
        email?: string
        error?: string
      }>
      refreshGoogleToken: (refreshToken: string) => Promise<{
        success: boolean
        token?: string
        error?: string
      }>
      callRedmineApi: (payload: {
        url: string
        method?: string
        headers?: Record<string, string>
        body?: string
        bodyBase64?: string
        responseType?: 'json' | 'text' | 'dataUrl'
      }) => Promise<{
        ok: boolean
        status: number
        statusText?: string
        data?: any
        error?: string
      }>
    }
  }
}
