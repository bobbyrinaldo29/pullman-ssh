import { ipcMain } from 'electron'
import type { SftpService } from './sftpService'

export class SshShellService {
  private shellStreams = new Map<string, any>()

  constructor(private sftpService: SftpService) {}

  public registerIpcHandlers(): void {
    ipcMain.handle(
      'ssh:shell-start',
      async (
        event,
        {
          sessionId,
          cols,
          rows,
          initialPath
        }: { sessionId: string; cols?: number; rows?: number; initialPath?: string }
      ) => {
        return this.startShell(
          sessionId,
          cols || 80,
          rows || 24,
          initialPath,
          (data) => {
            if (!event.sender.isDestroyed()) {
              event.sender.send(`ssh:shell-data:${sessionId}`, data)
            }
          },
          () => {
            if (!event.sender.isDestroyed()) {
              event.sender.send(`ssh:shell-close:${sessionId}`)
            }
          }
        )
      }
    )

    ipcMain.on(
      'ssh:shell-write',
      (_, { sessionId, data }: { sessionId: string; data: string }) => {
        this.writeShell(sessionId, data)
      }
    )

    ipcMain.on(
      'ssh:shell-resize',
      (
        _,
        {
          sessionId,
          cols,
          rows
        }: { sessionId: string; cols: number; rows: number }
      ) => {
        this.resizeShell(sessionId, cols, rows)
      }
    )

    ipcMain.handle('ssh:shell-close', (_, { sessionId }: { sessionId: string }) => {
      this.closeShell(sessionId)
      return { success: true }
    })
  }

  private formatCdCommand(pathStr?: string): string | null {
    if (!pathStr) return null
    const clean = pathStr.trim()
    if (!clean || clean === '~') return null
    if (clean.startsWith('~/')) {
      const sub = clean.slice(2).replace(/"/g, '\\"')
      return `cd "$HOME/${sub}"\n`
    }
    const escaped = clean.replace(/"/g, '\\"')
    return `cd "${escaped}"\n`
  }

  public async startShell(
    sessionId: string,
    cols: number,
    rows: number,
    initialPath?: string,
    onData?: (data: string) => void,
    onClose?: () => void
  ): Promise<{ success: boolean; message?: string }> {
    const session = this.sftpService.getSession(sessionId)
    if (!session || !session.isConnected) {
      return { success: false, message: 'SSH connection is not established yet.' }
    }

    // @ts-ignore
    const rawSsh = session.client?.client
    if (!rawSsh || typeof rawSsh.shell !== 'function') {
      return { success: false, message: 'Underlying SSH client does not support shell.' }
    }

    this.closeShell(sessionId)

    return new Promise((resolve) => {
      rawSsh.shell(
        {
          term: 'xterm-256color',
          cols: cols || 80,
          rows: rows || 24
        },
        (err: any, stream: any) => {
          if (err) {
            return resolve({
              success: false,
              message: err.message || 'Failed to open interactive shell stream'
            })
          }

          this.shellStreams.set(sessionId, stream)

          let navigated = false
          const cdCmd = this.formatCdCommand(initialPath)
          let fallbackTimer: NodeJS.Timeout | null = null

          const isPrompt = (rawText: string): boolean => {
            const clean = rawText.replace(/\u001b\[[0-9;]*[a-zA-Z]/g, '').trimEnd()
            return /[$#%>]$/.test(clean) || /[$#%>]\s+$/.test(clean)
          }

          const sendCdCommand = (): void => {
            if (navigated || !cdCmd) return
            navigated = true
            if (fallbackTimer) {
              clearTimeout(fallbackTimer)
              fallbackTimer = null
            }
            setTimeout(() => {
              try {
                if (stream && stream.writable) {
                  stream.write(cdCmd)
                }
              } catch (e) {
                console.error(`[SSH Shell navigate error ${sessionId}]:`, e)
              }
            }, 80)
          }

          stream.on('data', (data: Buffer | string) => {
            const str = data.toString()
            onData?.(str)
            if (!navigated && cdCmd && isPrompt(str)) {
              sendCdCommand()
            }
          })

          if (stream.stderr) {
            stream.stderr.on('data', (data: Buffer | string) => {
              const str = data.toString()
              onData?.(str)
              if (!navigated && cdCmd && isPrompt(str)) {
                sendCdCommand()
              }
            })
          }

          if (cdCmd) {
            fallbackTimer = setTimeout(() => {
              sendCdCommand()
            }, 2500)
          }

          stream.on('close', () => {
            if (fallbackTimer) {
              clearTimeout(fallbackTimer)
              fallbackTimer = null
            }
            this.shellStreams.delete(sessionId)
            onClose?.()
          })

          stream.on('error', (streamErr: any) => {
            console.error(`[SSH Shell Error ${sessionId}]:`, streamErr)
          })

          resolve({ success: true })
        }
      )
    })
  }

  public writeShell(sessionId: string, data: string): boolean {
    const stream = this.shellStreams.get(sessionId || 'default')
    if (stream && stream.writable) {
      stream.write(data)
      return true
    }
    return false
  }

  public resizeShell(sessionId: string, cols: number, rows: number): boolean {
    const stream = this.shellStreams.get(sessionId || 'default')
    if (stream && typeof stream.setWindow === 'function') {
      try {
        stream.setWindow(rows, cols, 0, 0)
        return true
      } catch {
        return false
      }
    }
    return false
  }

  public closeShell(sessionId?: string): void {
    const sid = sessionId || 'default'
    const stream = this.shellStreams.get(sid)
    if (stream) {
      try {
        stream.end()
      } catch {
        // ignore
      }
      this.shellStreams.delete(sid)
    }
  }
}

