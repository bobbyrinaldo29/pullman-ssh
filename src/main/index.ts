import { app, shell, BrowserWindow, ipcMain, net, dialog } from 'electron'
import { join, dirname } from 'path'
import { readFileSync, writeFileSync, existsSync } from 'fs'
import * as os from 'os'
import { Client as SshClient } from 'ssh2'
import mysql from 'mysql2/promise'
import { electronApp, optimizer, is } from '@electron-toolkit/utils'
import icon from '../../resources/icon.png?asset'
import { dbService, ConnectionInput } from './database'
import { sftpService } from './sftpService'
import { SshShellService } from './sshShellService'
import { ExternalEditorService } from './externalEditorService'
import { googleAuthService } from './googleAuthService'
import { redmineService } from './redmineService'
import { notificationService } from './notificationService'
import { extractDBeaverProjectFile, decryptDBeaverCredentialsNode } from './dbpExtractor'

function testSshConnection(input: {
  host: string
  port: number
  user: string
  password?: string
  timeoutMs?: number
}): Promise<{ success: boolean; message: string; latency?: number }> {
  return new Promise((resolve) => {
    const startTime = Date.now()
    const conn = new SshClient()
    let resolved = false
    const timeoutMs = input.timeoutMs || 8000

    const finish = (result: { success: boolean; message: string; latency?: number }): void => {
      if (!resolved) {
        resolved = true
        try {
          conn.end()
        } catch {
          // ignore
        }
        try {
          conn.destroy()
        } catch {
          // ignore
        }
        resolve(result)
      }
    }

    const timer = setTimeout(() => {
      finish({
        success: false,
        message: `Connection timed out after ${timeoutMs} ms connecting to ${input.host}:${input.port}.`
      })
    }, timeoutMs)

    conn.on('ready', () => {
      clearTimeout(timer)
      const latency = Date.now() - startTime
      finish({
        success: true,
        message: `SSH connection successful! Authenticated as "${input.user}" on ${input.host}:${input.port} (${latency} ms).`,
        latency
      })
    })

    conn.on('error', (err: unknown) => {
      clearTimeout(timer)
      const sshErr = err as { code?: string; level?: string; message?: string }
      const errMsg = sshErr?.message || 'Unknown SSH connection error'
      let message = errMsg

      if (
        sshErr?.level === 'client-authentication' ||
        errMsg.toLowerCase().includes('authentication') ||
        errMsg.toLowerCase().includes('auth failed')
      ) {
        message = `Authentication failed: Username "${input.user}" or password is incorrect.`
      } else if (sshErr?.code === 'ECONNREFUSED') {
        message = `Connection refused: Port ${input.port} on ${input.host} is closed or SSH daemon is not running.`
      } else if (sshErr?.code === 'ENOTFOUND') {
        message = `DNS lookup failed: Host "${input.host}" could not be resolved.`
      } else if (sshErr?.code === 'EHOSTUNREACH' || sshErr?.code === 'ENETUNREACH') {
        message = `Host unreachable: Unable to reach ${input.host}:${input.port}. Check network or VPN.`
      } else if (
        sshErr?.code === 'ETIMEDOUT' ||
        errMsg.toLowerCase().includes('timed out') ||
        errMsg.includes('handshake')
      ) {
        message = `Handshake timed out connecting to ${input.host}:${input.port}.`
      }

      finish({
        success: false,
        message
      })
    })

    conn.on('keyboard-interactive', (_name, _instructions, _instructionsLang, prompts, finishInteractive) => {
      if (prompts.length > 0 && input.password) {
        finishInteractive([input.password])
      } else {
        finishInteractive([])
      }
    })

    conn.on('timeout', () => {
      clearTimeout(timer)
      finish({
        success: false,
        message: `Socket timed out while connecting to ${input.host}:${input.port}.`
      })
    })

    try {
      conn.connect({
        host: input.host,
        port: input.port,
        username: input.user,
        password: input.password || undefined,
        tryKeyboard: Boolean(input.password),
        readyTimeout: timeoutMs,
        hostVerifier: () => true
      })
    } catch (err: unknown) {
      clearTimeout(timer)
      const errObj = err as { message?: string }
      finish({
        success: false,
        message: `Failed to initiate SSH connection: ${errObj?.message || String(err)}`
      })
    }
  })
}

function createSshTunnelStream(params: {
  sshHost: string
  sshPort: number
  sshUser: string
  sshPassword?: string
  targetHost: string
  targetPort: number
  timeoutMs: number
}): Promise<{ stream: any; close: () => void }> {
  return new Promise((resolve, reject) => {
    const conn = new SshClient()
    let closed = false
    let timer: NodeJS.Timeout | null = null

    const cleanup = (): void => {
      if (!closed) {
        closed = true
        if (timer) clearTimeout(timer)
        try {
          conn.end()
        } catch {
          // ignore
        }
        try {
          conn.destroy()
        } catch {
          // ignore
        }
      }
    }

    timer = setTimeout(() => {
      cleanup()
      reject(new Error(`SSH tunnel timed out connecting to ${params.sshHost}:${params.sshPort}`))
    }, params.timeoutMs)

    conn.on('ready', () => {
      conn.forwardOut(
        '127.0.0.1',
        0,
        params.targetHost,
        params.targetPort,
        (err, stream) => {
          if (timer) clearTimeout(timer)
          if (err) {
            cleanup()
            reject(err)
            return
          }
          stream.on('close', cleanup)
          resolve({
            stream,
            close: cleanup
          })
        }
      )
    })

    conn.on('error', (err) => {
      cleanup()
      reject(err)
    })

    conn.on('keyboard-interactive', (_name, _instructions, _instructionsLang, prompts, finishInteractive) => {
      if (prompts.length > 0 && params.sshPassword) {
        finishInteractive([params.sshPassword])
      } else {
        finishInteractive([])
      }
    })

    try {
      conn.connect({
        host: params.sshHost,
        port: params.sshPort,
        username: params.sshUser,
        password: params.sshPassword || undefined,
        tryKeyboard: Boolean(params.sshPassword),
        readyTimeout: params.timeoutMs,
        hostVerifier: () => true
      })
    } catch (err) {
      cleanup()
      reject(err)
    }
  })
}

async function testDatabaseConnection(input: {
  host: string
  port: number
  user: string
  password?: string
  database?: string
  timeoutMs?: number
  ssh?: {
    host: string
    port: number
    user: string
    password?: string
  }
}): Promise<{ success: boolean; message: string; latency?: number }> {
  const startTime = Date.now()
  const timeoutMs = input.timeoutMs || 8000
  let cleanupTunnel: (() => void) | null = null

  try {
    const connectionConfig: any = {
      user: input.user,
      password: input.password || undefined,
      database: input.database || undefined,
      connectTimeout: timeoutMs
    }

    const hasRemoteSsh =
      input.ssh?.host &&
      input.ssh.host.trim() !== '' &&
      input.ssh.host !== '127.0.0.1' &&
      input.ssh.host !== 'localhost'

    if (hasRemoteSsh && input.ssh) {
      // Connect through SSH tunnel to reach the database (e.g. 127.0.0.1:3306 on the remote server)
      const tunnel = await createSshTunnelStream({
        sshHost: input.ssh.host,
        sshPort: input.ssh.port,
        sshUser: input.ssh.user,
        sshPassword: input.ssh.password,
        targetHost: input.host,
        targetPort: input.port,
        timeoutMs
      })
      connectionConfig.stream = tunnel.stream
      cleanupTunnel = tunnel.close
    } else {
      connectionConfig.host = input.host
      connectionConfig.port = input.port
    }

    const conn = await mysql.createConnection(connectionConfig)
    await conn.ping()
    const latency = Date.now() - startTime
    await conn.end()
    if (cleanupTunnel) cleanupTunnel()

    const viaText = hasRemoteSsh ? ` (via SSH ${input.ssh?.host})` : ''
    return {
      success: true,
      message: `Database connection successful! Authenticated as "${input.user}" on ${input.host}:${input.port}${viaText}${input.database ? ` (database: ${input.database})` : ''} (${latency} ms).`,
      latency
    }
  } catch (err: unknown) {
    if (cleanupTunnel) cleanupTunnel()
    const dbErr = err as { code?: string; level?: string; message?: string }
    const code = dbErr?.code || 'ERROR'
    let message = dbErr?.message || 'Database connection error'

    if (dbErr?.level === 'client-authentication') {
      message = `SSH tunnel failed: Username or password is incorrect for SSH server "${input.ssh?.host}".`
    } else if (
      code === 'ER_ACCESS_DENIED_ERROR' ||
      message.toLowerCase().includes('access denied')
    ) {
      message = `Authentication failed: Access denied for database user "${input.user}" (check username and password).`
    } else if (code === 'ER_DBACCESS_DENIED_ERROR') {
      message = `Access denied for database user "${input.user}" to database "${input.database}".`
    } else if (code === 'ER_BAD_DB_ERROR') {
      message = `Database "${input.database}" does not exist on the server.`
    } else if (code === 'ECONNREFUSED') {
      message = `Connection refused: Database server is not running on ${input.host}:${input.port}.`
    } else if (code === 'ENOTFOUND') {
      message = `DNS lookup failed: Host "${input.host}" could not be resolved.`
    } else if (code === 'ETIMEDOUT') {
      message = `Connection timed out connecting to database on ${input.host}:${input.port}.`
    }

    return {
      success: false,
      message
    }
  }
}

function createWindow(): void {
  const isMac = process.platform === 'darwin'

  // Create the browser window.
  const mainWindow = new BrowserWindow({
    title: 'DO.MBA Pull Manager',
    width: 1200,
    height: 760,
    minWidth: 960,
    minHeight: 600,
    show: false,
    autoHideMenuBar: true,
    ...(isMac
      ? {
          titleBarStyle: 'hidden',
          trafficLightPosition: { x: 14, y: 12 }
        }
      : {
          frame: false
        }),
    ...(process.platform === 'linux' ? { icon } : {}),
    webPreferences: {
      preload: join(__dirname, '../preload/index.js'),
      sandbox: false,
      backgroundThrottling: false,
      spellcheck: false
    }
  })

  mainWindow.on('ready-to-show', () => {
    mainWindow.show()
  })

  mainWindow.on('maximize', () => {
    mainWindow.webContents.send('window-maximize-changed', true)
  })

  mainWindow.on('unmaximize', () => {
    mainWindow.webContents.send('window-maximize-changed', false)
  })

  mainWindow.webContents.setWindowOpenHandler((details) => {
    shell.openExternal(details.url)
    return { action: 'deny' }
  })

  // HMR for renderer base on electron-vite cli.
  // Load the remote URL for development or the local html file for production.
  if (is.dev && process.env['ELECTRON_RENDERER_URL']) {
    mainWindow.loadURL(process.env['ELECTRON_RENDERER_URL'])
  } else {
    mainWindow.loadFile(join(__dirname, '../renderer/index.html'))
  }
}

app.name = 'Pullman'
if (process.platform === 'darwin') {
  app.setName('Pullman')
}

// Performance & GPU Acceleration switches
app.commandLine.appendSwitch('enable-gpu-rasterization')
app.commandLine.appendSwitch('enable-zero-copy')
app.commandLine.appendSwitch('ignore-gpu-blocklist')

// This method will be called when Electron has finished
// initialization and is ready to create browser windows.
// Some APIs can only be used after this event occurs.
app.whenReady().then(() => {
  // Set app user model id for windows
  electronApp.setAppUserModelId('com.domba.pullmanager')

  // Default open or close DevTools by F12 in development
  // and ignore CommandOrControl + R in production.
  // see https://github.com/alex8088/electron-toolkit/tree/master/packages/utils
  app.on('browser-window-created', (_, window) => {
    optimizer.watchWindowShortcuts(window)
  })

  // Initialize SQLite Database
  dbService.init()

  // SQLite Connections IPC Handlers
  ipcMain.handle('connections:get-all', () => {
    return dbService.getAllConnections()
  })

  ipcMain.handle('connections:add', (_, input: ConnectionInput) => {
    return dbService.addConnection(input)
  })

  ipcMain.handle(
    'connections:update',
    (_, { id, input }: { id: number; input: ConnectionInput }) => {
      return dbService.updateConnection(id, input)
    }
  )

  ipcMain.handle(
    'connections:test',
    async (
      _,
      input: {
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
      }
    ) => {
      const type = input?.type || 'ssh'
      const targetHost = input?.host?.trim() || '127.0.0.1'
      const targetPort = Number(input?.port) || (type === 'database' ? 3306 : 22)
      const targetUser = input?.user?.trim() || 'root'
      const targetPassword = input?.password || ''
      const targetDatabase = input?.database?.trim() || ''

      if (type === 'database') {
        return testDatabaseConnection({
          host: targetHost,
          port: targetPort,
          user: targetUser,
          password: targetPassword,
          database: targetDatabase,
          timeoutMs: input?.timeoutMs,
          ssh: input?.ssh
        })
      }

      return testSshConnection({
        host: targetHost,
        port: targetPort,
        user: targetUser,
        password: targetPassword,
        timeoutMs: input?.timeoutMs
      })
    }
  )

  ipcMain.handle('connections:delete', (_, id: number) => {
    return dbService.deleteConnection(id)
  })

  ipcMain.handle(
    'connections:import-multiple',
    (_, inputs: ConnectionInput[], extraGroups?: string[]) => {
      return dbService.importMultipleConnections(inputs, extraGroups)
    }
  )

  // Dialog & File Transfer IPC Handlers for Import / Export
  ipcMain.handle(
    'dialog:open-file',
    async (
      _,
      options?: {
        title?: string
        filters?: { name: string; extensions: string[] }[]
      }
    ) => {
      const win = BrowserWindow.getFocusedWindow()
      const result = await dialog.showOpenDialog(win || (undefined as any), {
        title: options?.title || 'Open File',
        properties: ['openFile'],
        filters: options?.filters || [{ name: 'All Files', extensions: ['*'] }]
      })
      if (result.canceled || !result.filePaths.length) {
        return { canceled: true }
      }
      try {
        const filePath = result.filePaths[0]
        const buf = readFileSync(filePath)
        const isZip =
          filePath.toLowerCase().endsWith('.dbp') ||
          filePath.toLowerCase().endsWith('.zip') ||
          (buf.length >= 4 && buf[0] === 0x50 && buf[1] === 0x4b)
        if (isZip) {
          const extracted = extractDBeaverProjectFile(filePath)
          return { canceled: false, filePath, content: extracted.content, credentials: extracted.credentials }
        }
        const content = buf.toString('utf-8')
        return { canceled: false, filePath, content }
      } catch (err: any) {
        return { canceled: false, error: err.message || String(err) }
      }
    }
  )

  ipcMain.handle(
    'dialog:save-file',
    async (
      _,
      options: {
        title?: string
        defaultPath?: string
        content: string
        filters?: { name: string; extensions: string[] }[]
      }
    ) => {
      const win = BrowserWindow.getFocusedWindow()
      const result = await dialog.showSaveDialog(win || (undefined as any), {
        title: options.title || 'Save File',
        defaultPath: options.defaultPath,
        filters: options.filters || [{ name: 'All Files', extensions: ['*'] }]
      })
      if (result.canceled || !result.filePath) {
        return { canceled: true }
      }
      try {
        writeFileSync(result.filePath, options.content, 'utf-8')
        return { canceled: false, filePath: result.filePath }
      } catch (err: any) {
        return { canceled: false, error: err.message || String(err) }
      }
    }
  )

  ipcMain.handle('tools:detect-dbeaver', () => {
    const home = os.homedir()
    const candidates = [
      // macOS
      join(home, 'Library/DBeaverData/workspace6/General/.dbeaver/data-sources.json'),
      join(home, 'Library/DBeaverData/workspace6/.metadata/.plugins/org.jkiss.dbeaver.core/data-sources.json'),
      // Windows
      join(process.env.APPDATA || '', 'DBeaverData/workspace6/General/.dbeaver/data-sources.json'),
      // Linux
      join(home, '.local/share/DBeaverData/workspace6/General/.dbeaver/data-sources.json'),
      join(home, '.var/app/io.dbeaver.DBeaverCommunity/data/DBeaverData/workspace6/General/.dbeaver/data-sources.json')
    ]
    for (const p of candidates) {
      if (existsSync(p)) {
        try {
          const content = readFileSync(p, 'utf-8')
          let credentials: Record<string, any> | undefined
          const credPath = join(dirname(p), 'credentials-config.json')
          if (existsSync(credPath)) {
            try { credentials = decryptDBeaverCredentialsNode(readFileSync(credPath)) } catch { /* ignore */ }
          }
          return { found: true, path: p, content, credentials }
        } catch { /* ignore */ }
      }
    }
    return { found: false }
  })

  ipcMain.handle('tools:extract-dbeaver-dbp', (_, filePath: string) => {
    try {
      const res = extractDBeaverProjectFile(filePath)
      return { success: true, content: res.content, credentials: res.credentials }
    } catch (err: any) {
      return { success: false, error: err.message || String(err) }
    }
  })

  ipcMain.handle('tools:decrypt-dbeaver-credentials', (_, byteArr: number[]) => {
    try {
      return decryptDBeaverCredentialsNode(Buffer.from(byteArr))
    } catch {
      return {}
    }
  })

  // SQLite Connection Groups IPC Handlers
  ipcMain.handle('groups:get-all', () => {
    return dbService.getAllGroups()
  })

  ipcMain.handle('groups:add', (_, name: string) => {
    return dbService.addGroup(name)
  })

  ipcMain.handle('groups:rename', (_, oldName: string, newName: string) => {
    return dbService.renameGroup(oldName, newName)
  })

  ipcMain.handle('groups:delete', (_, name: string) => {
    return dbService.deleteGroup(name)
  })

  // SFTP & Local Filesystem Handlers (FileZilla-style)
  ipcMain.handle(
    'sftp:connect',
    (
      _,
      config: {
        sessionId?: string
        host: string
        port: number
        user: string
        password?: string
        timeoutMs?: number
        skipCwd?: boolean
      }
    ) => {
      return sftpService.connect(config)
    }
  )

  ipcMain.handle('sftp:disconnect', (_, sessionId?: string) => {
    return sftpService.disconnect(sessionId)
  })

  new SshShellService(sftpService).registerIpcHandlers()
  new ExternalEditorService(sftpService).registerIpcHandlers()

  ipcMain.handle('sftp:status', (_, sessionId?: string) => {
    return sftpService.getConnectedStatus(sessionId)
  })

  ipcMain.handle(
    'ssh:exec',
    (
      _,
      {
        command,
        sessionId,
        asSudo
      }: { command: string; sessionId?: string; asSudo?: boolean }
    ) => {
      return sftpService.execRemote(command, sessionId, asSudo)
    }
  )

  ipcMain.handle(
    'sftp:list-remote',
    (_, arg: string | { remotePath: string; sessionId?: string }) => {
      const remotePath = typeof arg === 'string' ? arg : arg.remotePath
      const sessionId = typeof arg === 'object' ? arg.sessionId : undefined
      return sftpService.listRemote(remotePath, sessionId)
    }
  )

  ipcMain.handle(
    'sftp:upload',
    (
      _,
      {
        localPath,
        remotePath,
        sessionId,
        asSudo
      }: { localPath: string; remotePath: string; sessionId?: string; asSudo?: boolean }
    ) => {
      return sftpService.upload(localPath, remotePath, sessionId, asSudo)
    }
  )

  ipcMain.handle(
    'sftp:download',
    (
      _,
      {
        remotePath,
        localPath,
        sessionId,
        asSudo
      }: { remotePath: string; localPath: string; sessionId?: string; asSudo?: boolean }
    ) => {
      return sftpService.download(remotePath, localPath, sessionId, asSudo)
    }
  )

  ipcMain.handle(
    'sftp:mkdir-remote',
    (_, arg: string | { remotePath: string; sessionId?: string; asSudo?: boolean }) => {
      const remotePath = typeof arg === 'string' ? arg : arg.remotePath
      const sessionId = typeof arg === 'object' ? arg.sessionId : undefined
      const asSudo = typeof arg === 'object' ? Boolean(arg.asSudo) : false
      return sftpService.mkdirRemote(remotePath, sessionId, asSudo)
    }
  )

  ipcMain.handle(
    'sftp:delete-remote',
    (
      _,
      {
        remotePath,
        isDirectory,
        sessionId,
        asSudo
      }: { remotePath: string; isDirectory?: boolean; sessionId?: string; asSudo?: boolean }
    ) => {
      return sftpService.deleteRemote(remotePath, isDirectory, sessionId, asSudo)
    }
  )

  ipcMain.handle(
    'sftp:rename-remote',
    (
      _,
      {
        oldPath,
        newPath,
        sessionId,
        asSudo
      }: { oldPath: string; newPath: string; sessionId?: string; asSudo?: boolean }
    ) => {
      return sftpService.renameRemote(oldPath, newPath, sessionId, asSudo)
    }
  )

  ipcMain.handle(
    'sftp:chmod-remote',
    (
      _,
      {
        remotePath,
        mode,
        sessionId,
        asSudo
      }: { remotePath: string; mode: string | number; sessionId?: string; asSudo?: boolean }
    ) => {
      return sftpService.chmodRemote(remotePath, mode, sessionId, asSudo)
    }
  )

  ipcMain.handle(
    'sftp:read-file',
    (
      _,
      {
        remotePath,
        sessionId,
        asSudo
      }: { remotePath: string; sessionId?: string; asSudo?: boolean }
    ) => {
      return sftpService.readFile(remotePath, sessionId, asSudo)
    }
  )

  ipcMain.handle(
    'sftp:write-file',
    (
      _,
      {
        remotePath,
        content,
        sessionId,
        asSudo
      }: { remotePath: string; content: string; sessionId?: string; asSudo?: boolean }
    ) => {
      return sftpService.writeFile(remotePath, content, sessionId, asSudo)
    }
  )

  ipcMain.handle(
    'sftp:get-git-info',
    (
      _,
      { remotePath, sessionId }: { remotePath: string; sessionId?: string }
    ) => {
      return sftpService.getGitInfo(remotePath, sessionId)
    }
  )

  ipcMain.handle(
    'sftp:get-git-blame',
    (
      _,
      { filePath, line, sessionId }: { filePath: string; line: number; sessionId?: string }
    ) => {
      return sftpService.getGitBlame(filePath, line, sessionId)
    }
  )

  ipcMain.handle(
    'sftp:get-git-status',
    (
      _,
      { remotePath, sessionId }: { remotePath: string; sessionId?: string }
    ) => {
      return sftpService.getGitStatus(remotePath, sessionId)
    }
  )

  ipcMain.handle(
    'sftp:git-commit',
    (
      _,
      { remotePath, message, sessionId }: { remotePath: string; message: string; sessionId?: string }
    ) => {
      return sftpService.gitCommit(remotePath, message, sessionId)
    }
  )

  ipcMain.handle('sftp:git-discard', (_, { filePath, sessionId }: { filePath: string; sessionId?: string }) =>
    sftpService.gitDiscard(filePath, sessionId)
  )

  ipcMain.handle('sftp:git-stage', (_, { filePath, staged, sessionId }: { filePath: string; staged: boolean; sessionId?: string }) =>
    sftpService.gitStage(filePath, staged, sessionId)
  )

  ipcMain.handle('sftp:git-stage-all', (_, { remotePath, sessionId }: { remotePath: string; sessionId?: string }) =>
    sftpService.gitStageAll(remotePath, sessionId)
  )

  ipcMain.handle('sftp:git-discard-all', (_, { remotePath, sessionId }: { remotePath: string; sessionId?: string }) =>
    sftpService.gitDiscardAll(remotePath, sessionId)
  )

  ipcMain.handle('sftp:git-pull', (_, { remotePath, sessionId }: { remotePath: string; sessionId?: string }) =>
    sftpService.gitPull(remotePath, sessionId)
  )

  ipcMain.handle('sftp:git-push', (_, { remotePath, sessionId }: { remotePath: string; sessionId?: string }) =>
    sftpService.gitPush(remotePath, sessionId)
  )

  ipcMain.handle(
    'sftp:git-cherry-pick',
    (_, { remotePath, hash, options, sessionId }: { remotePath: string; hash: string; options?: { autoPush?: boolean }; sessionId?: string }) =>
      sftpService.gitCherryPick(remotePath, hash, options, sessionId)
  )

  ipcMain.handle('sftp:git-cherry-pick-abort', (_, { remotePath, sessionId }: { remotePath: string; sessionId?: string }) =>
    sftpService.gitCherryPickAbort(remotePath, sessionId)
  )

  ipcMain.handle(
    'sftp:git-log',
    (_, { remotePath, sessionId }: { remotePath: string; sessionId?: string }) => {
      return sftpService.gitLog(remotePath, sessionId)
    }
  )

  ipcMain.handle(
    'sftp:git-graph-commits',
    (_, { remotePath, sessionId, limit }: { remotePath: string; sessionId?: string; limit?: number }) => {
      return sftpService.getGitGraphCommits(remotePath, sessionId, limit)
    }
  )

  ipcMain.handle(
    'sftp:git-commit-details',
    (_, { remotePath, hash, sessionId }: { remotePath: string; hash: string; sessionId?: string }) => {
      return sftpService.getCommitDetails(remotePath, hash, sessionId)
    }
  )

  ipcMain.handle(
    'sftp:git-file-diff',
    (_, { remotePath, hash, filePath, sessionId }: { remotePath: string; hash: string; filePath: string; sessionId?: string }) => {
      return sftpService.getGitFileDiff(remotePath, hash, filePath, sessionId)
    }
  )

  ipcMain.handle(
    'sftp:search-remote',
    (
      _,
      {
        query,
        rootPath,
        sessionId,
        isCaseSensitive,
        isWholeWord,
        isRegex
      }: {
        query: string
        rootPath: string
        sessionId?: string
        isCaseSensitive?: boolean
        isWholeWord?: boolean
        isRegex?: boolean
      }
    ) => {
      return sftpService.searchRemote(query, rootPath, sessionId, {
        isCaseSensitive,
        isWholeWord,
        isRegex
      })
    }
  )

  ipcMain.handle('sftp:rename-local', (_, { oldPath, newPath, asSudo }: { oldPath: string; newPath: string; asSudo?: boolean }) => sftpService.renameLocal(oldPath, newPath, asSudo))
  ipcMain.handle('sftp:open-local', (_, filePath: string) => shell.openPath(filePath))
  ipcMain.handle('sftp:get-local-home', () => sftpService.getLocalHome())
  ipcMain.handle('sftp:list-local', (_, dirPath: string) => sftpService.listLocal(dirPath))
  ipcMain.handle('sftp:mkdir-local', (_, arg: string | { dirPath: string; asSudo?: boolean }) => sftpService.mkdirLocal(typeof arg === 'string' ? arg : arg.dirPath, typeof arg === 'object' ? Boolean(arg.asSudo) : false))
  ipcMain.handle('sftp:delete-local', (_, arg: string | { filePath: string; asSudo?: boolean }) => sftpService.deleteLocal(typeof arg === 'string' ? arg : arg.filePath, typeof arg === 'object' ? Boolean(arg.asSudo) : false))

  ipcMain.handle('app:show-notification', (event, payload) =>
    notificationService.show(event, payload, icon)
  )

  // IPC test
  ipcMain.on('ping', () => console.log('pong'))

  // Windows / Frameless Window Controls
  ipcMain.on('window-minimize', (event) => BrowserWindow.fromWebContents(event.sender)?.minimize())
  ipcMain.on('window-maximize', (event) => {
    const win = BrowserWindow.fromWebContents(event.sender)
    if (win) win.isMaximized() ? win.unmaximize() : win.maximize()
  })
  ipcMain.on('window-close', (event) => BrowserWindow.fromWebContents(event.sender)?.close())
  ipcMain.handle('window-is-maximized', (event) => BrowserWindow.fromWebContents(event.sender)?.isMaximized() ?? false)

  ipcMain.handle(
    'ai:call-gemini',
    async (_, payload: { url: string; headers?: Record<string, string>; body: string }) => {
      try {
        const controller = new AbortController()
        const timer = setTimeout(() => controller.abort(), 45000)
        const res = await net.fetch(payload.url, {
          method: 'POST',
          headers: payload.headers || { 'Content-Type': 'application/json' },
          body: payload.body,
          signal: controller.signal
        }).finally(() => clearTimeout(timer))
        const status = res.status
        const ok = res.ok
        const data = await res.json().catch(() => null)
        return { ok, status, statusText: res.statusText, data }
      } catch (err) {
        return {
          ok: false,
          status: 0,
          error: err instanceof Error ? err.message : String(err)
        }
      }
    }
  )

  ipcMain.handle('ai:google-sign-in', () => googleAuthService.signIn())
  ipcMain.handle('ai:google-refresh-token', (_, refreshToken: string) => googleAuthService.refreshToken(refreshToken))

  ipcMain.handle(
    'redmine:request',
    (_, payload: { url: string; method?: string; headers?: Record<string, string>; body?: string; bodyBase64?: string; responseType?: 'json' | 'text' | 'dataUrl' }) =>
      redmineService.request(payload)
  )

  createWindow()

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})
