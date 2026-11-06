import { app, shell, BrowserWindow, ipcMain } from 'electron'
import { join } from 'path'
import { Client as SshClient } from 'ssh2'
import mysql from 'mysql2/promise'
import { electronApp, optimizer, is } from '@electron-toolkit/utils'
import icon from '../../resources/icon.png?asset'
import { dbService, ConnectionInput } from './database'
import { sftpService } from './sftpService'

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
      sandbox: false
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
        host: string
        port: number
        user: string
        password?: string
        timeoutMs?: number
      }
    ) => {
      return sftpService.connect(config)
    }
  )

  ipcMain.handle('sftp:disconnect', () => {
    return sftpService.disconnect()
  })

  ipcMain.handle('sftp:status', () => {
    return sftpService.getConnectedStatus()
  })

  ipcMain.handle('sftp:list-remote', (_, remotePath: string) => {
    return sftpService.listRemote(remotePath)
  })

  ipcMain.handle(
    'sftp:upload',
    (_, { localPath, remotePath }: { localPath: string; remotePath: string }) => {
      return sftpService.upload(localPath, remotePath)
    }
  )

  ipcMain.handle(
    'sftp:download',
    (_, { remotePath, localPath }: { remotePath: string; localPath: string }) => {
      return sftpService.download(remotePath, localPath)
    }
  )

  ipcMain.handle('sftp:mkdir-remote', (_, remotePath: string) => {
    return sftpService.mkdirRemote(remotePath)
  })

  ipcMain.handle(
    'sftp:delete-remote',
    (_, { remotePath, isDirectory }: { remotePath: string; isDirectory?: boolean }) => {
      return sftpService.deleteRemote(remotePath, isDirectory)
    }
  )

  ipcMain.handle(
    'sftp:rename-remote',
    (_, { oldPath, newPath }: { oldPath: string; newPath: string }) => {
      return sftpService.renameRemote(oldPath, newPath)
    }
  )

  ipcMain.handle('sftp:get-local-home', () => {
    return sftpService.getLocalHome()
  })

  ipcMain.handle('sftp:list-local', (_, dirPath: string) => {
    return sftpService.listLocal(dirPath)
  })

  ipcMain.handle('sftp:mkdir-local', (_, dirPath: string) => {
    return sftpService.mkdirLocal(dirPath)
  })

  ipcMain.handle('sftp:delete-local', (_, filePath: string) => {
    return sftpService.deleteLocal(filePath)
  })

  // IPC test
  ipcMain.on('ping', () => console.log('pong'))

  // Windows / Frameless Window Controls
  ipcMain.on('window-minimize', (event) => {
    const win = BrowserWindow.fromWebContents(event.sender)
    win?.minimize()
  })

  ipcMain.on('window-maximize', (event) => {
    const win = BrowserWindow.fromWebContents(event.sender)
    if (win) {
      if (win.isMaximized()) {
        win.unmaximize()
      } else {
        win.maximize()
      }
    }
  })

  ipcMain.on('window-close', (event) => {
    const win = BrowserWindow.fromWebContents(event.sender)
    win?.close()
  })

  ipcMain.handle('window-is-maximized', (event) => {
    const win = BrowserWindow.fromWebContents(event.sender)
    return win?.isMaximized() ?? false
  })

  createWindow()

  app.on('activate', function () {
    // On macOS it's common to re-create a window in the app when the
    // dock icon is clicked and there are no other windows open.
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

// Quit when all windows are closed, except on macOS. There, it's common
// for applications and their menu bar to stay active until the user quits
// explicitly with Cmd + Q.
app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})

// In this file you can include the rest of your app's specific main process
// code. You can also put them in separate files and require them here.
