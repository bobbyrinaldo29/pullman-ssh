import { BrowserWindow, ipcMain, Notification } from 'electron'
import { spawn, spawnSync, ChildProcess } from 'child_process'
import * as fs from 'fs'
import * as path from 'path'
import * as os from 'os'
import * as crypto from 'crypto'
import type { SftpService } from './sftpService'

export type ExternalEditorType = 'vscode' | 'cursor' | 'sublime' | 'notepad++' | 'custom'

export interface ExternalEditorInfo {
  id: ExternalEditorType
  name: string
  command: string
  detected: boolean
  executablePath?: string
}

export interface OpenExternalEditorPayload {
  sessionId?: string
  remotePath: string
  content?: string
  editorType?: ExternalEditorType
  customPath?: string
  customArgs?: string
  asSudo?: boolean
  line?: number
  autoSync?: boolean
}

interface WatchedFileRecord {
  localPath: string
  remotePath: string
  sessionId?: string
  asSudo?: boolean
  lastHash: string
  lastNonEmptySize: number
  isSyncing: boolean
  pendingSync: boolean
  isWritingLocal: boolean
  timer?: NodeJS.Timeout
  watcher?: fs.FSWatcher
  statListener?: fs.StatsListener
}

export class ExternalEditorService {
  private sftpService: SftpService
  private watchedFiles = new Map<string, WatchedFileRecord>()

  constructor(sftpService: SftpService) {
    this.sftpService = sftpService
  }

  public registerIpcHandlers(): void {
    ipcMain.handle('editor:detect-external-editors', async () => {
      return this.detectInstalledEditors()
    })

    ipcMain.handle('editor:open-in-external', async (_, payload: OpenExternalEditorPayload) => {
      return this.openFileInExternal(payload)
    })

    ipcMain.handle(
      'editor:test-external-launch',
      async (
        _,
        payload: {
          editorType: ExternalEditorType
          customPath?: string
          customArgs?: string
        }
      ) => {
        return this.testExternalLaunch(payload.editorType, payload.customPath, payload.customArgs)
      }
    )
  }

  public detectInstalledEditors(): ExternalEditorInfo[] {
    const isWin = process.platform === 'win32'
    const isMac = process.platform === 'darwin'
    const localAppData = process.env.LOCALAPPDATA || ''
    const programFiles = process.env['ProgramFiles'] || 'C:\\Program Files'
    const programFilesX86 = process.env['ProgramFiles(x86)'] || 'C:\\Program Files (x86)'

    const results: ExternalEditorInfo[] = [
      { id: 'vscode', name: 'Visual Studio Code', command: 'code', detected: false },
      { id: 'cursor', name: 'Cursor AI', command: 'cursor', detected: false },
      { id: 'sublime', name: 'Sublime Text', command: 'subl', detected: false },
      { id: 'notepad++', name: 'Notepad++', command: 'notepad++', detected: false },
      { id: 'custom', name: 'Custom Editor', command: '', detected: true }
    ]

    // Candidate paths for Windows
    const candidates: Record<ExternalEditorType, string[]> = {
      vscode: isWin
        ? [
            path.join(localAppData, 'Programs', 'Microsoft VS Code', 'Code.exe'),
            path.join(localAppData, 'Programs', 'Microsoft VS Code', 'bin', 'code.cmd'),
            path.join(programFiles, 'Microsoft VS Code', 'Code.exe'),
            path.join(programFiles, 'Microsoft VS Code', 'bin', 'code.cmd'),
            path.join(programFilesX86, 'Microsoft VS Code', 'Code.exe')
          ]
        : isMac
          ? ['/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code']
          : ['/usr/bin/code', '/usr/local/bin/code', '/snap/bin/code'],
      cursor: isWin
        ? [
            path.join(localAppData, 'Programs', 'cursor', 'Cursor.exe'),
            path.join(localAppData, 'Programs', 'cursor', 'resources', 'app', 'bin', 'cursor.cmd'),
            path.join(programFiles, 'cursor', 'Cursor.exe')
          ]
        : isMac
          ? ['/Applications/Cursor.app/Contents/Resources/app/bin/cursor']
          : ['/usr/bin/cursor', '/usr/local/bin/cursor'],
      sublime: isWin
        ? [
            path.join(programFiles, 'Sublime Text', 'sublime_text.exe'),
            path.join(programFiles, 'Sublime Text 3', 'sublime_text.exe'),
            path.join(programFilesX86, 'Sublime Text 3', 'sublime_text.exe')
          ]
        : isMac
          ? ['/Applications/Sublime Text.app/Contents/SharedSupport/bin/subl']
          : ['/usr/bin/subl', '/usr/bin/sublime-text'],
      'notepad++': isWin
        ? [
            path.join(programFiles, 'Notepad++', 'notepad++.exe'),
            path.join(programFilesX86, 'Notepad++', 'notepad++.exe')
          ]
        : [],
      custom: []
    }

    for (const item of results) {
      if (item.id === 'custom') continue
      const list = candidates[item.id] || []
      for (const p of list) {
        if (p && fs.existsSync(p)) {
          item.detected = true
          item.executablePath = p
          break
        }
      }
      // If not found in known paths, check if command exists in PATH
      if (!item.detected && this.checkInPath(item.command)) {
        item.detected = true
        item.executablePath = item.command
      }
    }

    return results
  }

  private checkInPath(cmd: string): boolean {
    if (!cmd) return false
    try {
      const isWin = process.platform === 'win32'
      const checkCmd = isWin ? 'where.exe' : 'which'
      const res = spawnSync(checkCmd, [cmd], { stdio: 'ignore' })
      return res.status === 0
    } catch {
      return false
    }
  }

  public resolveExecutable(
    type: ExternalEditorType,
    customPath?: string
  ): { executable: string; isShellScript: boolean } {
    if (type === 'custom') {
      const exec = (customPath || '').trim()
      if (!exec) throw new Error('No custom executable path provided in settings.')
      return { executable: exec, isShellScript: /\.cmd$|\.bat$/i.test(exec) }
    }

    if (customPath && customPath.trim()) {
      const exec = customPath.trim()
      return { executable: exec, isShellScript: /\.cmd$|\.bat$/i.test(exec) }
    }

    const detected = this.detectInstalledEditors().find((e) => e.id === type)
    if (detected?.executablePath) {
      return {
        executable: detected.executablePath,
        isShellScript: /\.cmd$|\.bat$/i.test(detected.executablePath)
      }
    }

    // Fallbacks
    switch (type) {
      case 'vscode':
        return { executable: 'code', isShellScript: process.platform === 'win32' }
      case 'cursor':
        return { executable: 'cursor', isShellScript: process.platform === 'win32' }
      case 'sublime':
        return { executable: 'subl', isShellScript: false }
      case 'notepad++':
        return { executable: 'notepad++', isShellScript: false }
      default:
        return { executable: 'code', isShellScript: process.platform === 'win32' }
    }
  }

  public async openFileInExternal(payload: OpenExternalEditorPayload): Promise<{
    success: boolean
    localPath: string
    message?: string
  }> {
    const {
      remotePath,
      sessionId,
      editorType = 'vscode',
      customPath,
      customArgs,
      asSudo = false,
      line,
      autoSync = true
    } = payload

    if (!remotePath) {
      throw new Error('Remote path is required to open file in external editor.')
    }

    const normalizedRemote = remotePath.trim().replace(/\/+/g, '/').replace(/^([^/])/, '/$1')

    // 1. Fetch remote content if not provided
    let content = payload.content
    let effectiveSudo = asSudo
    const hasValidPayloadContent = typeof content === 'string' && content.length > 0

    if (!hasValidPayloadContent) {
      try {
        content = await this.sftpService.readFile(normalizedRemote, sessionId, effectiveSudo)
      } catch (err) {
        if (!effectiveSudo) {
          try {
            content = await this.sftpService.readFile(normalizedRemote, sessionId, true)
            effectiveSudo = true
          } catch {
            throw err
          }
        } else {
          throw err
        }
      }
    }

    // 2. Prepare local cache path
    const tempRoot = path.join(os.tmpdir(), 'pullman_external')
    const safeSession = (sessionId || 'default').replace(/[^a-zA-Z0-9_-]/g, '_')
    const safeRel = normalizedRemote.replace(/^[/\\]+/, '').replace(/[\\/:]+/g, path.sep)
    const localFilePath = path.join(tempRoot, safeSession, safeRel)

    const dir = path.dirname(localFilePath)
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true })
    }

    // Pause existing watcher during local cache write so we don't trigger a redundant echo upload
    const existingRecord = this.watchedFiles.get(localFilePath)
    if (existingRecord) {
      existingRecord.isWritingLocal = true
    }

    try {
      // Ensure existing local file is writable before overwriting
      if (fs.existsSync(localFilePath)) {
        try {
          fs.chmodSync(localFilePath, 0o666)
        } catch {}
      }

      // 3. Write content to local file with binary fidelity & fallback
      if (hasValidPayloadContent && content !== undefined) {
        fs.writeFileSync(localFilePath, content, 'utf8')
      } else {
        let downloaded = false
        try {
          await this.sftpService.download(normalizedRemote, localFilePath, sessionId, effectiveSudo)
          downloaded = fs.existsSync(localFilePath) && fs.statSync(localFilePath).size > 0
        } catch {}

        if (!downloaded) {
          fs.writeFileSync(localFilePath, content || '', 'utf8')
        }

        // If still 0 bytes, try reading shell cat output as final safeguard
        if (fs.existsSync(localFilePath) && fs.statSync(localFilePath).size === 0) {
          try {
            const cleanPath = normalizedRemote.replace(/\/+/g, '/').replace(/'/g, "'\\''")
            const catRes = await this.sftpService.execRemote(`cat '${cleanPath}'`, sessionId, effectiveSudo)
            if (catRes.code === 0 && catRes.stdout.length > 0) {
              content = catRes.stdout
              fs.writeFileSync(localFilePath, content, 'utf8')
            }
          } catch {}
        }
      }

      // Guarantee file is writable by VS Code on Windows
      try {
        fs.chmodSync(localFilePath, 0o666)
      } catch {}

      if (fs.existsSync(localFilePath)) {
        try {
          content = fs.readFileSync(localFilePath, 'utf8')
        } catch {}
      }
    } finally {
      if (existingRecord) {
        existingRecord.isWritingLocal = false
      }
    }

    const finalContent = content || ''
    const initialHash = crypto.createHash('md5').update(finalContent, 'utf8').digest('hex')
    const initialSize = Buffer.byteLength(finalContent, 'utf8')

    // 4. Setup auto-sync watcher (recreate cleanly so stale/broken watchers are always healed)
    if (autoSync) {
      this.setupFileWatcher(localFilePath, normalizedRemote, sessionId, effectiveSudo, initialHash, initialSize)
    }

    // 5. Launch external editor
    const { executable, isShellScript } = this.resolveExecutable(editorType, customPath)
    const args = this.buildLaunchArgs(editorType, localFilePath, line, customArgs)

    try {
      const child = this.spawnEditorProcess(executable, args, isShellScript)
      await new Promise<void>((resolve, reject) => {
        const timer = setTimeout(() => {
          child.unref()
          resolve()
        }, 200)

        child.once('error', (err) => {
          clearTimeout(timer)
          reject(err)
        })

        child.once('exit', (code) => {
          if (code !== null && code !== 0) {
            clearTimeout(timer)
            reject(new Error(`Editor process exited immediately with error code ${code}`))
          }
        })
      })
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : String(err)
      throw new Error(`Failed to launch editor "${executable}": ${errMsg}`, { cause: err })
    }

    return {
      success: true,
      localPath: localFilePath,
      message: `File opened in ${editorType.toUpperCase()}`
    }
  }

  private buildLaunchArgs(
    type: ExternalEditorType,
    localPath: string,
    line?: number,
    customArgs?: string
  ): string[] {
    if (customArgs && customArgs.trim()) {
      const trimmed = customArgs.trim()

      // If user typed only a number (e.g. "33"), treat it as line number jump
      if (/^\d+$/.test(trimmed)) {
        const lineNum = parseInt(trimmed, 10)
        switch (type) {
          case 'vscode':
          case 'cursor':
            return ['-g', `${localPath}:${lineNum}`]
          case 'sublime':
            return [`${localPath}:${lineNum}`]
          case 'notepad++':
            return [localPath, `-n${lineNum}`]
          default:
            return [localPath]
        }
      }

      // Tokenize customArgs safely preserving quoted substrings
      const rawTokens = trimmed.match(/[^\s"']+|"([^"]*)"|'([^']*)'/g) || []
      const tokens = rawTokens.map((t) => t.replace(/^["']|["']$/g, ''))
      const hasFilePlaceholder = tokens.some((t) => t.includes('{file}'))

      const resolvedTokens = tokens.map((t) => {
        return t
          .replace('{file}', localPath)
          .replace('{line}', String(line || 1))
      })

      if (hasFilePlaceholder) {
        return resolvedTokens
      }

      // If {file} wasn't explicitly placed, append localPath according to editor standard
      switch (type) {
        case 'vscode':
        case 'cursor':
          return line ? [...resolvedTokens, '-g', `${localPath}:${line}`] : [...resolvedTokens, localPath]
        case 'sublime':
          return line ? [...resolvedTokens, `${localPath}:${line}`] : [...resolvedTokens, localPath]
        case 'notepad++':
          return line ? [...resolvedTokens, localPath, `-n${line}`] : [...resolvedTokens, localPath]
        default:
          return [...resolvedTokens, localPath]
      }
    }

    switch (type) {
      case 'vscode':
      case 'cursor':
        return line ? ['-g', `${localPath}:${line}`] : [localPath]
      case 'sublime':
        return line ? [`${localPath}:${line}`] : [localPath]
      case 'notepad++':
        return line ? [localPath, `-n${line}`] : [localPath]
      default:
        return [localPath]
    }
  }

  private cleanupWatcher(localPath: string): void {
    const existing = this.watchedFiles.get(localPath)
    if (!existing) return
    if (existing.timer) clearTimeout(existing.timer)
    if (existing.watcher) {
      try {
        existing.watcher.close()
      } catch {}
    }
    if (existing.statListener) {
      try {
        fs.unwatchFile(localPath, existing.statListener)
      } catch {}
    }
    this.watchedFiles.delete(localPath)
  }

  private setupFileWatcher(
    localPath: string,
    remotePath: string,
    sessionId?: string,
    asSudo = false,
    initialHash: string = '',
    initialSize: number = 0
  ): void {
    // Always cleanly replace existing watcher so broken/stale Windows watchers are healed
    this.cleanupWatcher(localPath)

    const record: WatchedFileRecord = {
      localPath,
      remotePath,
      sessionId,
      asSudo,
      lastHash: initialHash,
      lastNonEmptySize: initialSize,
      isSyncing: false,
      pendingSync: false,
      isWritingLocal: false
    }

    const scheduleSync = (): void => {
      if (record.isWritingLocal) return
      if (record.timer) clearTimeout(record.timer)
      record.timer = setTimeout(() => {
        this.syncWatchedFile(record).catch((err) => {
          console.error(`[ExternalEditor] Unexpected sync error for ${record.remotePath}:`, err)
        })
      }, 350)
    }

    const dir = path.dirname(localPath)
    const targetBase = path.basename(localPath)
    const isWin = process.platform === 'win32'

    // 1. Watch parent directory (does NOT lock localPath on Windows and survives VS Code atomic renames!)
    try {
      const watcher = fs.watch(dir, (_eventType, filename) => {
        if (filename) {
          const nameStr = filename.toString()
          const matches = isWin
            ? nameStr.toLowerCase() === targetBase.toLowerCase()
            : nameStr === targetBase
          if (!matches) return
        }
        scheduleSync()
      })
      watcher.on('error', (err) => {
        console.warn(`[ExternalEditor] Directory watcher error for ${dir}:`, err)
      })
      record.watcher = watcher
    } catch (err) {
      console.warn(`[ExternalEditor] Could not watch directory ${dir}:`, err)
    }

    // 2. Stat polling fallback (guarantees save detection even if Windows ReadDirectoryChangesW drops events)
    const statListener: fs.StatsListener = (curr, prev) => {
      if (curr.mtimeMs !== prev.mtimeMs || curr.size !== prev.size) {
        scheduleSync()
      }
    }
    try {
      fs.watchFile(localPath, { interval: 600, persistent: false }, statListener)
      record.statListener = statListener
    } catch (err) {
      console.warn(`[ExternalEditor] Could not attach stat watcher for ${localPath}:`, err)
    }

    this.watchedFiles.set(localPath, record)
  }

  private async syncWatchedFile(record: WatchedFileRecord): Promise<void> {
    if (record.isWritingLocal) return
    if (record.isSyncing) {
      record.pendingSync = true
      return
    }

    if (!fs.existsSync(record.localPath)) return

    let updatedContent: string
    try {
      updatedContent = fs.readFileSync(record.localPath, 'utf8')
    } catch {
      return
    }

    // Protect against mid-write 0-byte truncation race on Windows (e.g. VS Code writing buffer)
    if (updatedContent.length === 0 && record.lastNonEmptySize > 0) {
      await new Promise((r) => setTimeout(r, 400))
      if (!fs.existsSync(record.localPath)) return
      try {
        updatedContent = fs.readFileSync(record.localPath, 'utf8')
      } catch {
        return
      }
    }

    const currentHash = crypto.createHash('md5').update(updatedContent, 'utf8').digest('hex')
    if (currentHash === record.lastHash) return

    record.isSyncing = true
    record.pendingSync = false
    const fileName = path.posix.basename(record.remotePath)

    try {
      let usedSudo = Boolean(record.asSudo)
      try {
        await this.sftpService.writeFile(
          record.remotePath,
          updatedContent,
          record.sessionId,
          usedSudo
        )
      } catch (primaryErr) {
        if (!usedSudo) {
          // Automatic sudo fallback for remote files owned by root/www-data that are world-readable
          try {
            await this.sftpService.writeFile(
              record.remotePath,
              updatedContent,
              record.sessionId,
              true
            )
            usedSudo = true
            record.asSudo = true
          } catch (sudoErr) {
            const sudoMsg = sudoErr instanceof Error ? sudoErr.message : String(sudoErr)
            // If user lacks sudoers privilege, preserve the clearer primary error
            if (
              sudoMsg.toLowerCase().includes('not allowed to execute') ||
              sudoMsg.toLowerCase().includes('not in the sudoers')
            ) {
              throw primaryErr
            }
            throw sudoErr
          }
        } else {
          throw primaryErr
        }
      }

      // Only update lastHash AFTER remote write succeeds!
      record.lastHash = currentHash
      if (updatedContent.length > 0) {
        record.lastNonEmptySize = Buffer.byteLength(updatedContent, 'utf8')
      }

      for (const win of BrowserWindow.getAllWindows()) {
        if (!win.isDestroyed()) {
          win.webContents.send('editor:external-sync-complete', {
            remotePath: record.remotePath,
            sessionId: record.sessionId,
            content: updatedContent,
            asSudo: usedSudo,
            timestamp: Date.now()
          })
        }
      }

      try {
        if (Notification.isSupported()) {
          new Notification({
            title: usedSudo ? 'Synced as Sudo (VS Code)' : 'Synced to Server (VS Code)',
            body: `Saved "${fileName}" to remote server.`,
            silent: true
          }).show()
        }
      } catch {}
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : String(err)
      console.error(`[ExternalEditor] Sync error for ${record.remotePath}:`, err)

      for (const win of BrowserWindow.getAllWindows()) {
        if (!win.isDestroyed()) {
          win.webContents.send('editor:external-sync-error', {
            remotePath: record.remotePath,
            sessionId: record.sessionId,
            error: errMsg,
            timestamp: Date.now()
          })
        }
      }

      try {
        if (Notification.isSupported()) {
          new Notification({
            title: 'Save Failed (VS Code)',
            body: `Failed to save "${fileName}": ${errMsg}`
          }).show()
        }
      } catch {}
    } finally {
      record.isSyncing = false
      if (record.pendingSync) {
        record.pendingSync = false
        setTimeout(() => {
          this.syncWatchedFile(record).catch(() => {})
        }, 150)
      }
    }
  }

  private spawnEditorProcess(
    executable: string,
    args: string[],
    isShellScript: boolean
  ): ChildProcess {
    const isWin = process.platform === 'win32'
    if (isWin) {
      const isCmdOrBat = /\.cmd$|\.bat$/i.test(executable)
      const hasPathSep = executable.includes('\\') || executable.includes('/')
      const isBareCommand = !hasPathSep && !/\.exe$/i.test(executable)

      if (isShellScript || isCmdOrBat || isBareCommand) {
        const target = executable.includes(' ') ? `"${executable}"` : executable
        return spawn('cmd.exe', ['/c', target, ...args], {
          detached: true,
          stdio: 'ignore',
          windowsVerbatimArguments: true
        })
      }
    }

    return spawn(executable, args, {
      detached: true,
      stdio: 'ignore',
      shell: false
    })
  }

  public async testExternalLaunch(
    editorType: ExternalEditorType,
    customPath?: string,
    customArgs?: string
  ): Promise<{ success: boolean; message: string }> {
    try {
      const { executable, isShellScript } = this.resolveExecutable(editorType, customPath)
      const tempTestFile = path.join(os.tmpdir(), 'pullman_editor_test.txt')
      fs.writeFileSync(
        tempTestFile,
        `Pullman SSH External Editor Test\nDate: ${new Date().toISOString()}\nEditor: ${editorType}\nPath: ${executable}\n`,
        'utf8'
      )

      const args = this.buildLaunchArgs(editorType, tempTestFile, 1, customArgs)
      const child = this.spawnEditorProcess(executable, args, isShellScript)

      return await new Promise<{ success: boolean; message: string }>((resolve) => {
        let finished = false

        const timer = setTimeout(() => {
          if (!finished) {
            finished = true
            child.unref()
            resolve({
              success: true,
              message: `Successfully launched ${editorType.toUpperCase()} (${path.basename(executable)})!`
            })
          }
        }, 600)

        child.once('error', (err) => {
          if (!finished) {
            finished = true
            clearTimeout(timer)
            resolve({
              success: false,
              message: `Failed to launch ${editorType.toUpperCase()}: ${err.message}`
            })
          }
        })

        child.once('exit', (code) => {
          if (!finished && code !== null && code !== 0) {
            finished = true
            clearTimeout(timer)
            resolve({
              success: false,
              message: `Editor process exited with code ${code}. Please verify executable path and arguments.`
            })
          }
        })
      })
    } catch (err) {
      return {
        success: false,
        message: err instanceof Error ? err.message : String(err)
      }
    }
  }
}
