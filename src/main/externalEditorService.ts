import { BrowserWindow, ipcMain } from 'electron'
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
  timer?: NodeJS.Timeout
  watcher?: fs.FSWatcher
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

    // 1. Fetch remote content if not provided
    let content = payload.content
    if (typeof content !== 'string') {
      content = await this.sftpService.readFile(remotePath, sessionId, asSudo)
    }

    // 2. Prepare local cache path
    const tempRoot = path.join(os.tmpdir(), 'pullman_external')
    const safeSession = (sessionId || 'default').replace(/[^a-zA-Z0-9_-]/g, '_')
    const safeRel = remotePath.replace(/^[/\\]+/, '').replace(/[\\/:]+/g, path.sep)
    const localFilePath = path.join(tempRoot, safeSession, safeRel)

    const dir = path.dirname(localFilePath)
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true })
    }

    // 3. Write content to local file
    const initialHash = crypto.createHash('md5').update(content, 'utf8').digest('hex')
    fs.writeFileSync(localFilePath, content, 'utf8')

    // 4. Setup auto-sync watcher
    if (autoSync) {
      this.setupFileWatcher(localFilePath, remotePath, sessionId, asSudo, initialHash)
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
      return customArgs
        .replace('{file}', localPath)
        .replace('{line}', String(line || 1))
        .split(' ')
        .filter(Boolean)
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

  private setupFileWatcher(
    localPath: string,
    remotePath: string,
    sessionId?: string,
    asSudo = false,
    initialHash: string = ''
  ): void {
    const existing = this.watchedFiles.get(localPath)
    if (existing) {
      existing.remotePath = remotePath
      existing.sessionId = sessionId
      existing.asSudo = asSudo
      existing.lastHash = initialHash
      return
    }

    const record: WatchedFileRecord = {
      localPath,
      remotePath,
      sessionId,
      asSudo,
      lastHash: initialHash
    }

    try {
      const watcher = fs.watch(localPath, (eventType) => {
        if (eventType !== 'change' && eventType !== 'rename') return
        if (record.timer) clearTimeout(record.timer)

        record.timer = setTimeout(async () => {
          try {
            if (!fs.existsSync(localPath)) return
            const updatedContent = fs.readFileSync(localPath, 'utf8')
            const currentHash = crypto
              .createHash('md5')
              .update(updatedContent, 'utf8')
              .digest('hex')

            if (currentHash === record.lastHash) return
            record.lastHash = currentHash

            await this.sftpService.writeFile(
              record.remotePath,
              updatedContent,
              record.sessionId,
              record.asSudo
            )

            // Broadcast sync event to renderer so active tabs can update their buffer
            for (const win of BrowserWindow.getAllWindows()) {
              if (!win.isDestroyed()) {
                win.webContents.send('editor:external-sync-complete', {
                  remotePath: record.remotePath,
                  sessionId: record.sessionId,
                  content: updatedContent,
                  timestamp: Date.now()
                })
              }
            }
          } catch (err) {
            console.error(`[ExternalEditor] Sync error for ${record.remotePath}:`, err)
          }
        }, 300)
      })

      record.watcher = watcher
      this.watchedFiles.set(localPath, record)
    } catch (err) {
      console.warn(`[ExternalEditor] Could not watch ${localPath}:`, err)
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
