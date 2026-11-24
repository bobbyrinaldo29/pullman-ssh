import SftpClient from 'ssh2-sftp-client'
import { promises as fs } from 'fs'
import * as path from 'path'

export interface SftpFileItem {
  name: string
  path: string
  isDirectory: boolean
  size: number
  modifyTime: number
  permissions?: string
  permissionsMode?: string
  author?: string
  owner?: string
  group?: string
  type: string
}

import { localFileService, LocalFileItem } from './localFileService'
import { SftpSearchService } from './sftpSearchService'
import { SftpGitService } from './sftpGitService'
import { GitCredentials } from './sftpGitAuthHelper'
export type { LocalFileItem, GitCredentials }

export interface SftpSession {
  client: SftpClient
  isConnected: boolean
  cwd?: string
  config?: { sessionId?: string; host: string; port: number; user: string; password?: string; timeoutMs?: number; skipCwd?: boolean }
}

export class SftpService {
  private sessions = new Map<string, SftpSession>()
  private lastConfigs = new Map<string, { sessionId?: string; host: string; port: number; user: string; password?: string; timeoutMs?: number; skipCwd?: boolean }>()
  private dirCache = new Map<string, { items: SftpFileItem[]; timestamp: number }>()

  public clearDirCache(sessionId?: string): void {
    if (sessionId) {
      for (const k of this.dirCache.keys()) {
        if (k.startsWith(`${sessionId}:`)) this.dirCache.delete(k)
      }
    } else {
      this.dirCache.clear()
    }
  }

  public getSession(sessionId?: string): SftpSession | undefined {
    return this.sessions.get(sessionId || 'default')
  }

  private requireSession(sessionId?: string): SftpSession {
    const s = this.getSession(sessionId)
    if (!s || !s.isConnected) throw new Error('SFTP client is not connected.')
    return s
  }

  public getConnectedStatus(sessionId?: string): boolean {
    const session = this.getSession(sessionId)
    return Boolean(session?.isConnected)
  }

  public async connect(config: {
    sessionId?: string
    host: string
    port: number
    user: string
    password?: string
    timeoutMs?: number
    skipCwd?: boolean
  }): Promise<{ success: boolean; message: string; cwd?: string }> {
    const sid = config.sessionId || 'default'
    this.lastConfigs.set(sid, { ...config, sessionId: sid })
    await this.disconnect(sid)
    const client = new SftpClient()

    try {
      // Attach keyboard-interactive listener to underlying ssh2 client
      // @ts-ignore
      const rawSsh = client.client
      if (rawSsh && typeof rawSsh.on === 'function') {
        rawSsh.on(
          'keyboard-interactive',
          (_name: string, _instructions: string, _lang: string, prompts: any[], finishInteractive: (answers: string[]) => void) => {
            if (prompts && prompts.length > 0 && config.password) {
              finishInteractive([config.password])
            } else {
              finishInteractive([])
            }
          }
        )
      }

      await client.connect({
        host: config.host,
        port: config.port,
        username: config.user,
        password: config.password || undefined,
        // @ts-ignore
        tryKeyboard: Boolean(config.password),
        readyTimeout: config.timeoutMs || 10000,
        keepaliveInterval: 0,
        // @ts-ignore
        hostVerifier: () => true
      })

      let cwd = '/'
      if (!config.skipCwd) {
        try {
          cwd = await Promise.race([
            client.cwd(),
            new Promise<string>((_, reject) =>
              setTimeout(() => reject(new Error('cwd timeout')), 400)
            )
          ])
        } catch {
          cwd = '/'
        }
      }

      this.sessions.set(sid, {
        client,
        isConnected: true,
        cwd: cwd || '/',
        config: { ...config }
      })

      return {
        success: true,
        message: `Connected to ${config.user}@${config.host}:${config.port}`,
        cwd: cwd || '/'
      }
    } catch (err: unknown) {
      this.sessions.delete(sid)
      const errMsg = err instanceof Error ? err.message : String(err)
      return {
        success: false,
        message: `SFTP Connection failed: ${errMsg}`
      }
    }
  }

  public async disconnect(sessionId?: string): Promise<void> {
    const sid = sessionId || 'default'
    const session = this.sessions.get(sid)
    if (session) {
      try {
        await session.client.end()
      } catch {
        // ignore
      }
      this.sessions.delete(sid)
    }
  }

  public async listRemote(remotePath: string, sessionId?: string): Promise<SftpFileItem[]> {
    const session = this.getSession(sessionId)
    if (!session || !session.isConnected) {
      throw new Error('SFTP client is not connected.')
    }

    const cleanInputPath = (remotePath || '/').trim()
    let targetPath = cleanInputPath.startsWith('/') ? cleanInputPath : `/${cleanInputPath}`
    targetPath = targetPath.replace(/\/+/g, '/')

    const sid = sessionId || 'default'
    const cacheKey = `${sid}:${targetPath}`
    const cached = this.dirCache.get(cacheKey)
    if (cached && Date.now() - cached.timestamp < 3500) {
      return cached.items
    }

    let rawList: any[] = []
    try {
      rawList = await session.client.list(targetPath)
    } catch (err: unknown) {
      // If trailing slash was missing, try with trailing slash
      if (!targetPath.endsWith('/')) {
        try {
          rawList = await session.client.list(`${targetPath}/`)
        } catch {
          // If that failed, try resolving realPath in case of symlinks
          try {
            const resolved = await session.client.realPath(targetPath)
            rawList = await session.client.list(resolved)
          } catch {
            throw err
          }
        }
      } else {
        const noSlash = targetPath.slice(0, -1) || '/'
        try {
          rawList = await session.client.list(noSlash)
        } catch {
          throw err
        }
      }
    }

    const parseMode = (u: string, g: string, o: string) => {
      const d = (s: string) => (s.includes('r') ? 4 : 0) + (s.includes('w') ? 2 : 0) + (/[xst]/i.test(s) ? 1 : 0)
      const r = (s: string) => (s.includes('r') ? 'r' : '-') + (s.includes('w') ? 'w' : '-') + (/[xst]/i.test(s) ? (s.includes('s') ? 's' : s.includes('t') ? 't' : 'x') : '-')
      return { octal: `${d(u)}${d(g)}${d(o)}`, rwx: `${r(u)}${r(g)}${r(o)}` }
    }

    const items: SftpFileItem[] = rawList.map((item) => {
      const isDir = item.type === 'd' || item.type === 'l'
      const baseDir = targetPath === '/' ? '' : (targetPath.endsWith('/') ? targetPath.slice(0, -1) : targetPath)
      const fullPath = `${baseDir}/${item.name}`
      const rights = item.rights || { user: '', group: '', other: '' }
      const { octal, rwx } = parseMode(rights.user || '', rights.group || '', rights.other || '')

      let parsedOwner = ''
      let parsedGroup = ''
      if (item.longname) {
        const parts = item.longname.trim().split(/\s+/)
        if (parts.length >= 4 && /^[drwxstcbspl\-]{10}/i.test(parts[0])) {
          parsedOwner = parts[2] || ''
          parsedGroup = parts[3] || ''
        }
      }

      if (!parsedOwner && item.owner !== undefined && item.owner !== null) {
        parsedOwner = String(item.owner)
      }
      if (!parsedGroup && item.group !== undefined && item.group !== null) {
        parsedGroup = String(item.group)
      }

      const author = parsedOwner || parsedGroup || '-'

      return {
        name: item.name,
        path: fullPath,
        isDirectory: isDir,
        size: item.size || 0,
        modifyTime: item.modifyTime || 0,
        permissions: rwx,
        permissionsMode: octal,
        author,
        owner: parsedOwner,
        group: parsedGroup,
        type: item.type
      }
    })

    const sorted = items.sort((a, b) => {
      if (a.isDirectory && !b.isDirectory) return -1
      if (!a.isDirectory && b.isDirectory) return 1
      return a.name.localeCompare(b.name)
    })

    this.dirCache.set(cacheKey, { items: sorted, timestamp: Date.now() })
    return sorted
  }

  public async execRemote(
    command: string,
    sessionId?: string,
    asSudo = false,
    sudoPassword?: string
  ): Promise<{ stdout: string; stderr: string; code: number }> {
    const session = this.getSession(sessionId)
    if (!session || !session.isConnected) {
      throw new Error('SFTP client is not connected.')
    }

    // @ts-ignore
    const rawSsh = session.client.client
    if (!rawSsh || typeof rawSsh.exec !== 'function') {
      throw new Error('Underlying SSH client connection is not available.')
    }

    const isRoot = session.config?.user === 'root'
    const password = (sudoPassword !== undefined && sudoPassword !== null && sudoPassword !== '')
      ? sudoPassword
      : (session.config?.password || '')

    let cmdToRun = command
    let feedStdin = false

    if (asSudo && !isRoot) {
      const esc = command.replace(/'/g, "'\\''")
      if (password) {
        const escPass = password.replace(/'/g, "'\\''")
        cmdToRun = `printf '%s\\n' '${escPass}' | sudo -S -p '' su -c '${esc}'`
      } else {
        cmdToRun = `sudo -n su -c '${esc}'`
      }
    }

    return new Promise((resolve, reject) => {
      rawSsh.exec(cmdToRun, { pty: false }, (err: any, stream: any) => {
        if (err) return reject(err)
        let stdout = ''
        let stderr = ''
        let exitCode = 0

        if (feedStdin && password) {
          try {
            stream.write(password + '\n')
          } catch {
            // ignore
          }
        }

        stream.on('data', (data: Buffer) => {
          stdout += data.toString()
        })
        stream.stderr.on('data', (data: Buffer) => {
          stderr += data.toString()
        })
        stream.on('exit', (code: number) => {
          exitCode = typeof code === 'number' ? code : 0
        })
        stream.on('close', () => {
          resolve({ stdout, stderr, code: exitCode })
        })
      })
    })
  }

  public async upload(localPath: string, remotePath: string, sessionId?: string, asSudo = false): Promise<void> {
    const session = this.getSession(sessionId)
    if (!session || !session.isConnected) {
      throw new Error('SFTP client is not connected.')
    }
    const target = remotePath.replace(/\/+/g, '/')
    const stat = await fs.stat(localPath)

    if (asSudo) {
      const isRoot = session.config?.user === 'root'
      if (!isRoot) {
        const tmpRemoteName = `/tmp/pullman_up_${Date.now()}_${path.basename(localPath)}`
        if (stat.isDirectory()) {
          await session.client.uploadDir(localPath, tmpRemoteName)
        } else {
          try {
            await session.client.put(localPath, tmpRemoteName)
          } catch {
            await session.client.fastPut(localPath, tmpRemoteName)
          }
        }
        const escTmp = tmpRemoteName.replace(/'/g, "'\\''")
        const escTarget = target.replace(/'/g, "'\\''")
        const parentDir = path.posix.dirname(target).replace(/'/g, "'\\''")
        await this.execRemote(`mkdir -p '${parentDir}' && cp -rf '${escTmp}' '${escTarget}' && rm -rf '${escTmp}'`, sessionId, true)
        return
      }
    }

    if (stat.isDirectory()) {
      await session.client.uploadDir(localPath, target)
    } else {
      try {
        await session.client.put(localPath, target)
      } catch {
        await session.client.fastPut(localPath, target)
      }
    }
  }

  public async download(remotePath: string, localPath: string, sessionId?: string, asSudo = false): Promise<void> {
    const session = this.getSession(sessionId)
    if (!session || !session.isConnected) {
      throw new Error('SFTP client is not connected.')
    }
    const source = remotePath.replace(/\/+/g, '/')

    if (asSudo) {
      const isRoot = session.config?.user === 'root'
      if (!isRoot) {
        const tmpRemoteName = `/tmp/pullman_dl_${Date.now()}_${path.basename(source)}`
        const escSource = source.replace(/'/g, "'\\''")
        const escTmp = tmpRemoteName.replace(/'/g, "'\\''")
        await this.execRemote(`cp -rf '${escSource}' '${escTmp}' && chmod -R 777 '${escTmp}'`, sessionId, true)

        try {
          let isDir = false
          try {
            const stat = await session.client.stat(tmpRemoteName)
            isDir = stat.isDirectory
          } catch {
            // ignore
          }
          if (isDir) {
            await session.client.downloadDir(tmpRemoteName, localPath)
          } else {
            await session.client.get(tmpRemoteName, localPath)
          }
        } finally {
          try {
            await this.execRemote(`rm -rf '${escTmp}'`, sessionId, true)
          } catch {
            // ignore
          }
        }
        return
      }
    }

    try {
      const stat = await session.client.stat(source)
      if (stat.isDirectory) {
        await session.client.downloadDir(source, localPath)
      } else {
        await session.client.get(source, localPath)
      }
    } catch {
      await session.client.get(source, localPath)
    }
  }

  public async mkdirRemote(remotePath: string, sessionId?: string, asSudo = false): Promise<void> {
    const session = this.requireSession(sessionId)
    const target = remotePath.replace(/\/+/g, '/')
    if (asSudo) {
      const escTarget = target.replace(/'/g, "'\\''")
      const res = await this.execRemote(`mkdir -p '${escTarget}'`, sessionId, true)
      if (res.code !== 0) throw new Error((res.stderr || res.stdout || '').trim() || `Create directory as sudo failed (exit code: ${res.code})`)
      return
    }
    await session.client.mkdir(target, true)
  }

  public async deleteRemote(remotePath: string, isDirectory = false, sessionId?: string, asSudo = false): Promise<void> {
    const session = this.requireSession(sessionId), target = remotePath.replace(/\/+/g, '/')
    if (asSudo) {
      const res = await this.execRemote(`rm -rf '${target.replace(/'/g, "'\\''")}'`, sessionId, true)
      if (res.code !== 0) throw new Error((res.stderr || res.stdout || '').trim() || `Delete as sudo failed (exit code: ${res.code})`)
      return
    }
    if (isDirectory) await session.client.rmdir(target, true)
    else await session.client.delete(target)
  }

  public async renameRemote(oldPath: string, newPath: string, sessionId?: string, asSudo = false): Promise<void> {
    const session = this.requireSession(sessionId), cleanOld = oldPath.replace(/\/+/g, '/'), cleanNew = newPath.replace(/\/+/g, '/')
    if (asSudo) {
      const res = await this.execRemote(`mv '${cleanOld.replace(/'/g, "'\\''")}' '${cleanNew.replace(/'/g, "'\\''")}'`, sessionId, true)
      if (res.code !== 0) throw new Error((res.stderr || res.stdout || '').trim() || `Rename as sudo failed (exit code: ${res.code})`)
      return
    }
    await session.client.rename(cleanOld, cleanNew)
  }

  public async chmodRemote(remotePath: string, mode: number | string, sessionId?: string, asSudo = false): Promise<void> {
    const session = this.requireSession(sessionId)
    const cleanPath = remotePath.replace(/\/+/g, '/')
    const modeStr = String(mode).replace(/^0+/, '') || '0'
    if (asSudo) {
      const esc = cleanPath.replace(/'/g, "'\\''")
      const res = await this.execRemote(`chmod ${modeStr} '${esc}'`, sessionId, true)
      if (res.code !== 0) throw new Error((res.stderr || res.stdout || '').trim() || `Chmod as sudo failed (exit code: ${res.code})`)
      return
    }
    const numericMode = parseInt(modeStr, 8)
    await session.client.chmod(cleanPath, numericMode)
  }

  public async readFile(remotePath: string, sessionId?: string, asSudo = false): Promise<string> {
    let session = this.requireSession(sessionId)
    const cleanPath = remotePath.replace(/\/+/g, '/')
    if (asSudo && session.config?.user !== 'root') {
      const res = await this.execRemote(`cat '${cleanPath.replace(/'/g, "'\\''")}'`, sessionId, true)
      if (res.code !== 0) throw new Error((res.stderr || res.stdout || '').trim() || `Read as sudo failed (exit code: ${res.code})`)
      return res.stdout
    }
    try {
      const res = await session.client.get(cleanPath)
      return Buffer.isBuffer(res) ? res.toString('utf-8') : String(res)
    } catch (err) {
      // Fast fallback: read file content using remote SSH shell directly
      try {
        let catRes = await this.execRemote(`cat '${cleanPath.replace(/'/g, "'\\''")}'`, sessionId, asSudo)
        if (catRes.code === 0) return catRes.stdout
        if (session.config?.password || session.config?.user !== 'root') {
          catRes = await this.execRemote(`cat '${cleanPath.replace(/'/g, "'\\''")}'`, sessionId, true)
          if (catRes.code === 0) return catRes.stdout
        }
      } catch {
        // exec fallback failed, continue to reconnect
      }

      if (session.config) {
        try {
          const connRes = await this.connect(session.config)
          if (connRes.success) {
            session = this.requireSession(sessionId)
            const retry = await session.client.get(cleanPath)
            return Buffer.isBuffer(retry) ? retry.toString('utf-8') : String(retry)
          }
        } catch {
          // ignore reconnect error and throw original
        }
      }
      throw err
    }
  }

  public async writeFile(
    remotePath: string,
    content: string,
    sessionId?: string,
    asSudo = false,
    sudoPassword?: string
  ): Promise<void> {
    const sid = sessionId || 'default'
    let session = this.getSession(sid)
    if (!session || !session.isConnected) {
      const savedCfg = this.lastConfigs.get(sid)
      if (savedCfg) {
        const connRes = await this.connect({ ...savedCfg, sessionId: sid })
        if (connRes.success) {
          session = this.getSession(sid)
        }
      }
    }
    if (!session || !session.isConnected) {
      throw new Error('SFTP client is not connected.')
    }
    if (sudoPassword && session.config) {
      session.config.password = sudoPassword
    }
    const cleanPath = remotePath.replace(/\/+/g, '/'), buffer = Buffer.from(content, 'utf-8')
    const doWrite = async (s: SftpSession): Promise<void> => {
      if (asSudo && s.config?.user !== 'root') {
        const currentUser = s.config?.user || ''
        const escClean = cleanPath.replace(/'/g, "'\\''")
        const parentDir = path.posix.dirname(cleanPath)
        const escParentDir = parentDir.replace(/'/g, "'\\''")

        // 1. Get original permissions mode, owner, and group
        let origFileMode = ''
        let origFileOwner = ''
        let origFileGroup = ''
        let origParentMode = ''
        let fileExists = false

        try {
          const statFile = await this.execRemote(
            `stat -c '%a:%U:%G' '${escClean}' 2>/dev/null || stat -f '%Lp:%Su:%Sg' '${escClean}' 2>/dev/null`,
            sessionId,
            false
          )
          if (statFile.code === 0 && statFile.stdout.trim()) {
            const parts = statFile.stdout.trim().split(':')
            if (parts.length >= 1 && parts[0]) {
              origFileMode = parts[0].trim()
              origFileOwner = parts[1]?.trim() || ''
              origFileGroup = parts[2]?.trim() || ''
              fileExists = true
            }
          }
        } catch {}

        if (!fileExists) {
          try {
            const statSudo = await this.execRemote(
              `stat -c '%a:%U:%G' '${escClean}' 2>/dev/null || stat -f '%Lp:%Su:%Sg' '${escClean}' 2>/dev/null`,
              sessionId,
              true,
              sudoPassword
            )
            if (statSudo.code === 0 && statSudo.stdout.trim()) {
              const parts = statSudo.stdout.trim().split(':')
              if (parts.length >= 1 && parts[0]) {
                origFileMode = parts[0].trim()
                origFileOwner = parts[1]?.trim() || ''
                origFileGroup = parts[2]?.trim() || ''
                fileExists = true
              }
            }
          } catch {}
        }
        if (!fileExists) {
          try {
            const testRes = await this.execRemote(`test -f '${escClean}'`, sessionId, true, sudoPassword)
            if (testRes.code === 0) fileExists = true
          } catch {}
        }

        try {
          const statParent = await this.execRemote(
            `stat -c '%a' '${escParentDir}' 2>/dev/null || stat -f '%Lp' '${escParentDir}' 2>/dev/null`,
            sessionId,
            false
          )
          if (statParent.code === 0 && statParent.stdout.trim()) {
            origParentMode = statParent.stdout.trim().split('\n')[0].trim()
          }
        } catch {}

        let lastError: Error | null = null

        // =========================================================================
        // Strategy 1: CHMOD 777 (User requested)
        // Temporarily chmod 777 so user can write natively over SFTP, then restore
        // =========================================================================
        try {
          if (fileExists) {
            const chmodRes = await this.execRemote(`chmod 777 '${escClean}'`, sessionId, true, sudoPassword)
            if (chmodRes.code !== 0) {
              throw new Error((chmodRes.stderr || chmodRes.stdout || '').trim() || `chmod 777 failed (code ${chmodRes.code})`)
            }
          } else {
            await this.execRemote(`mkdir -p '${escParentDir}'`, sessionId, true, sudoPassword)
            const chmodP = await this.execRemote(`chmod 777 '${escParentDir}'`, sessionId, true, sudoPassword)
            if (chmodP.code !== 0) {
              throw new Error((chmodP.stderr || chmodP.stdout || '').trim() || `chmod parent dir failed (code ${chmodP.code})`)
            }
          }

          if (currentUser) {
            await this.execRemote(`chown ${currentUser} '${escClean}'`, sessionId, true, sudoPassword).catch(() => {})
          }

          await s.client.put(buffer, cleanPath)

          // SUCCESS with chmod 777! Restore original permissions
          try {
            const restoreMode = origFileMode || '644'
            await this.execRemote(`chmod ${restoreMode} '${escClean}'`, sessionId, true, sudoPassword)
            if (origFileOwner && origFileGroup) {
              await this.execRemote(`chown ${origFileOwner}:${origFileGroup} '${escClean}'`, sessionId, true, sudoPassword).catch(() => {})
            }
          } catch {}

          if (!fileExists && origParentMode) {
            try {
              await this.execRemote(`chmod ${origParentMode} '${escParentDir}'`, sessionId, true, sudoPassword)
            } catch {}
          }

          return
        } catch (err) {
          lastError = err instanceof Error ? err : new Error(String(err))
          if (origFileMode) {
            await this.execRemote(`chmod ${origFileMode} '${escClean}'`, sessionId, true, sudoPassword).catch(() => {})
          }
          if (!fileExists && origParentMode) {
            await this.execRemote(`chmod ${origParentMode} '${escParentDir}'`, sessionId, true, sudoPassword).catch(() => {})
          }
        }

        // =========================================================================
        // Strategy 2: DIRECT SUDO CP (via /tmp file with direct binary cp -f)
        // =========================================================================
        try {
          await this.execRemote(`mkdir -p '${escParentDir}'`, sessionId, true, sudoPassword)
          const tmpRemote = `/tmp/pullman_edit_${Date.now()}`
          await s.client.put(buffer, tmpRemote)
          const escTmp = tmpRemote.replace(/'/g, "'\\''")

          try {
            await this.execRemote(`chmod 777 '${escClean}'`, sessionId, true, sudoPassword).catch(() => {})
            const cpRes = await this.execRemote(`cp -f '${escTmp}' '${escClean}'`, sessionId, true, sudoPassword)

            if (cpRes.code === 0) {
              if (origFileMode) {
                await this.execRemote(`chmod ${origFileMode} '${escClean}'`, sessionId, true, sudoPassword).catch(() => {})
              }
              if (origFileOwner && origFileGroup) {
                await this.execRemote(`chown ${origFileOwner}:${origFileGroup} '${escClean}'`, sessionId, true, sudoPassword).catch(() => {})
              }
              return
            } else {
              const errDetail = (cpRes.stderr || cpRes.stdout || '').trim()
              lastError = new Error(errDetail || `cp -f failed with exit code ${cpRes.code}`)
            }

            // =========================================================================
            // Strategy 3: DIRECT SUDO DD (alternative binary to cp)
            // =========================================================================
            const ddRes = await this.execRemote(`dd if='${escTmp}' of='${escClean}' bs=64k`, sessionId, true, sudoPassword)
            if (ddRes.code === 0) {
              if (origFileMode) {
                await this.execRemote(`chmod ${origFileMode} '${escClean}'`, sessionId, true, sudoPassword).catch(() => {})
              }
              return
            }
          } finally {
            try {
              await s.client.delete(tmpRemote)
            } catch {
              await this.execRemote(`rm -f '${escTmp}'`, sessionId, false)
            }
          }
        } catch (err) {
          lastError = err instanceof Error ? err : new Error(String(err))
        }

        throw lastError || new Error(`Failed to save "${cleanPath}" with sudo privileges.`)
      }
      await s.client.put(buffer, cleanPath)
    }
    try {
      await doWrite(session)
    } catch (err) {
      const msg = (err instanceof Error ? err.message : String(err)).toLowerCase()
      const isPermOrFsErr =
        msg.includes('permission denied') ||
        msg.includes('eacces') ||
        msg.includes('eperm') ||
        msg.includes('access denied') ||
        msg.includes('not allowed to execute') ||
        msg.includes('not in the sudoers') ||
        msg.includes('incorrect password') ||
        msg.includes('no such file')
      const reconnectCfg = session.config || this.lastConfigs.get(sid)
      if (!isPermOrFsErr && reconnectCfg) {
        const connRes = await this.connect({ ...reconnectCfg, sessionId: sid })
        if (connRes.success) {
          session = this.requireSession(sid)
          await doWrite(session)
          return
        }
      }
      throw err
    }
  }

    public renameLocal(oldPath: string, newPath: string, asSudo = false): Promise<void> { return localFileService.renameLocal(oldPath, newPath, asSudo) }
  public mkdirLocal(dirPath: string, asSudo = false): Promise<void> { return localFileService.mkdirLocal(dirPath, asSudo) }
  public deleteLocal(filePath: string, asSudo = false): Promise<void> { return localFileService.deleteLocal(filePath, asSudo) }
  public getLocalHome(): string { return localFileService.getLocalHome() }
  public listLocal(dirPath: string): Promise<LocalFileItem[]> { return localFileService.listLocal(dirPath) }

  private gitService = new SftpGitService(this)

  public getGitInfo(remotePath: string, sessionId?: string) {
    return this.gitService.getGitInfo(remotePath, sessionId)
  }

  public getGitStatus(remotePath: string, sessionId?: string) {
    return this.gitService.getGitStatus(remotePath, sessionId)
  }

  public gitCommit(remotePath: string, message: string, sessionId?: string) {
    return this.gitService.gitCommit(remotePath, message, sessionId)
  }

  public gitDiscard(filePath: string, sessionId?: string) {
    return this.gitService.gitDiscard(filePath, sessionId)
  }

  public gitStage(filePath: string, staged: boolean, sessionId?: string) {
    return this.gitService.gitStage(filePath, staged, sessionId)
  }

  public gitStageAll(remotePath: string, sessionId?: string) {
    return this.gitService.gitStageAll(remotePath, sessionId)
  }

  public gitDiscardAll(remotePath: string, sessionId?: string) {
    return this.gitService.gitDiscardAll(remotePath, sessionId)
  }

  public gitPull(remotePath: string, sessionId?: string, credentials?: GitCredentials) {
    return this.gitService.gitPull(remotePath, sessionId, credentials)
  }

  public gitPush(remotePath: string, sessionId?: string, credentials?: GitCredentials) {
    return this.gitService.gitPush(remotePath, sessionId, credentials)
  }

  public gitCherryPick(
    remotePath: string,
    hash: string,
    options?: { autoPush?: boolean; credentials?: GitCredentials },
    sessionId?: string
  ) {
    return this.gitService.gitCherryPick(remotePath, hash, options, sessionId)
  }

  public gitCherryPickAbort(remotePath: string, sessionId?: string) {
    return this.gitService.gitCherryPickAbort(remotePath, sessionId)
  }

  public gitLog(remotePath: string, sessionId?: string) {
    return this.gitService.gitLog(remotePath, sessionId)
  }

  public getGitGraphCommits(remotePath: string, sessionId?: string, limit = 80) {
    return this.gitService.getGitGraphCommits(remotePath, sessionId, limit)
  }

  public getCommitDetails(remotePath: string, hash: string, sessionId?: string) {
    return this.gitService.getCommitDetails(remotePath, hash, sessionId)
  }

  public getGitFileDiff(remotePath: string, hash: string, filePath: string, sessionId?: string) {
    return this.gitService.getGitFileDiff(remotePath, hash, filePath, sessionId)
  }

  private searchService = new SftpSearchService(this)

  public async searchRemote(
    query: string,
    rootPath: string,
    sessionId?: string,
    options?: { isCaseSensitive?: boolean; isWholeWord?: boolean; isRegex?: boolean }
  ): Promise<{ file: string; line: number; text: string }[]> {
    return this.searchService.searchRemote(query, rootPath, sessionId, options)
  }

  public async getGitBlame(
    filePath: string,
    line: number,
    sessionId?: string
  ): Promise<{ author: string; timeAgo: string; summary: string; hash: string; isUncommitted: boolean } | null> {
    return this.searchService.getGitBlame(filePath, line, sessionId)
  }
}

export const sftpService = new SftpService()

