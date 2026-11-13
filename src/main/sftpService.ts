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
export type { LocalFileItem }

interface SftpSession {
  client: SftpClient
  isConnected: boolean
  cwd?: string
  config?: {
    host: string
    port: number
    user: string
    password?: string
    timeoutMs?: number
  }
}

export class SftpService {
  private sessions = new Map<string, SftpSession>()

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
        keepaliveInterval: 10000,
        keepaliveCountMax: 3,
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

    const items: SftpFileItem[] = rawList.map((item) => {
      // Recognize both 'd' (directory) and 'l' (symlink) as directory navigable
      const isDir = item.type === 'd' || item.type === 'l'
      const baseDir = targetPath === '/' ? '' : (targetPath.endsWith('/') ? targetPath.slice(0, -1) : targetPath)
      const fullPath = `${baseDir}/${item.name}`

      const rights = item.rights || { user: '', group: '', other: '' }
      const u = rights.user || ''
      const g = rights.group || ''
      const o = rights.other || ''

      const getOctalDigit = (str: string): number => {
        let val = 0
        if (str.includes('r')) val += 4
        if (str.includes('w')) val += 2
        if (str.includes('x') || str.includes('s') || str.includes('t')) val += 1
        return val
      }

      const getRwxPart = (str: string): string => {
        return (
          (str.includes('r') ? 'r' : '-') +
          (str.includes('w') ? 'w' : '-') +
          (str.includes('x') ? 'x' : str.includes('s') ? 's' : str.includes('t') ? 't' : '-')
        )
      }

      const octal = `${getOctalDigit(u)}${getOctalDigit(g)}${getOctalDigit(o)}`
      const rwx = `${getRwxPart(u)}${getRwxPart(g)}${getRwxPart(o)}`

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

    return items.sort((a, b) => {
      if (a.isDirectory && !b.isDirectory) return -1
      if (!a.isDirectory && b.isDirectory) return 1
      return a.name.localeCompare(b.name)
    })
  }

  public async execRemote(
    command: string,
    sessionId?: string,
    asSudo = false
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
    const password = session.config?.password || ''

    let cmdToRun = command
    let feedStdin = false

    if (asSudo && !isRoot) {
      if (password) {
        cmdToRun = `sudo -S -p '' -- ${command}`
        feedStdin = true
      } else {
        cmdToRun = `sudo -n -- ${command}`
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
      await this.execRemote(`mkdir -p '${escTarget}'`, sessionId, true)
      return
    }
    await session.client.mkdir(target, true)
  }

  public async deleteRemote(remotePath: string, isDirectory = false, sessionId?: string, asSudo = false): Promise<void> {
    const session = this.requireSession(sessionId)
    const target = remotePath.replace(/\/+/g, '/')
    if (asSudo) {
      const escTarget = target.replace(/'/g, "'\\''")
      await this.execRemote(`rm -rf '${escTarget}'`, sessionId, true)
      return
    }
    if (isDirectory) {
      await session.client.rmdir(target, true)
    } else {
      await session.client.delete(target)
    }
  }

  public async renameRemote(oldPath: string, newPath: string, sessionId?: string, asSudo = false): Promise<void> {
    const session = this.requireSession(sessionId)
    const cleanOld = oldPath.replace(/\/+/g, '/')
    const cleanNew = newPath.replace(/\/+/g, '/')
    if (asSudo) {
      const escOld = cleanOld.replace(/'/g, "'\\''")
      const escNew = cleanNew.replace(/'/g, "'\\''")
      await this.execRemote(`mv '${escOld}' '${escNew}'`, sessionId, true)
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
      await this.execRemote(`chmod ${modeStr} '${esc}'`, sessionId, true)
      return
    }
    const numericMode = parseInt(modeStr, 8)
    await session.client.chmod(cleanPath, numericMode)
  }

  public async readFile(remotePath: string, sessionId?: string, asSudo = false): Promise<string> {
    const session = this.requireSession(sessionId)
    const cleanPath = remotePath.replace(/\/+/g, '/')
    if (asSudo && session.config?.user !== 'root') {
      const esc = cleanPath.replace(/'/g, "'\\''")
      const res = await this.execRemote(`cat '${esc}'`, sessionId, true)
      return res.stdout
    }
    const res = await session.client.get(cleanPath)
    if (Buffer.isBuffer(res)) {
      return res.toString('utf-8')
    }
    return String(res)
  }

  public async writeFile(remotePath: string, content: string, sessionId?: string, asSudo = false): Promise<void> {
    const session = this.requireSession(sessionId)
    const cleanPath = remotePath.replace(/\/+/g, '/')
    const buffer = Buffer.from(content, 'utf-8')
    if (asSudo && session.config?.user !== 'root') {
      const tmpRemote = `/tmp/pullman_edit_${Date.now()}`
      await session.client.put(buffer, tmpRemote)
      const escTmp = tmpRemote.replace(/'/g, "'\\''")
      const escTarget = cleanPath.replace(/'/g, "'\\''")
      await this.execRemote(`cp -f '${escTmp}' '${escTarget}' && rm -f '${escTmp}'`, sessionId, true)
      return
    }
    await session.client.put(buffer, cleanPath)
  }

  public renameLocal(oldPath: string, newPath: string, asSudo = false): Promise<void> {
    return localFileService.renameLocal(oldPath, newPath, asSudo)
  }

  public mkdirLocal(dirPath: string, asSudo = false): Promise<void> {
    return localFileService.mkdirLocal(dirPath, asSudo)
  }

  public deleteLocal(filePath: string, asSudo = false): Promise<void> {
    return localFileService.deleteLocal(filePath, asSudo)
  }

  public getLocalHome(): string {
    return localFileService.getLocalHome()
  }

  public listLocal(dirPath: string): Promise<LocalFileItem[]> {
    return localFileService.listLocal(dirPath)
  }

  private gitCd(remotePath: string): string {
    const clean = (remotePath || '/').replace(/^diff:/, '').replace(/\/+/g, '/')
    const esc = clean.replace(/'/g, "'\\''")
    return `PATH=$PATH:/usr/local/bin:/usr/bin:/bin; P='${esc}'; if [ -d "$P" ]; then cd "$P" 2>/dev/null; else cd "$(dirname "$P")" 2>/dev/null; fi`
  }

  public async getGitInfo(
    remotePath: string,
    sessionId?: string
  ): Promise<{ isGit: boolean; branch: string; isDirty: boolean }> {
    const session = this.getSession(sessionId)
    if (!session || !session.isConnected) {
      return { isGit: false, branch: '', isDirty: false }
    }
    try {
      const cd = this.gitCd(remotePath)
      const cmd = `${cd} && git -c safe.directory=* rev-parse --is-inside-work-tree 2>/dev/null && git -c safe.directory=* rev-parse --abbrev-ref HEAD 2>/dev/null || true`
      const res = await this.execRemote(cmd, sessionId, false)
      const lines = res.stdout.trim().split('\n').map((l) => l.trim()).filter(Boolean)
      if (lines.length === 0) {
        return { isGit: false, branch: '', isDirty: false }
      }
      const isInside = lines.includes('true')
      const branch = lines.find((l) => l !== 'true') || ''
      if (!isInside && !branch) {
        return { isGit: false, branch: '', isDirty: false }
      }

      let isDirty = false
      try {
        const statusRes = await this.execRemote(
          `${cd} && git -c safe.directory=* status --porcelain 2>/dev/null | head -n 1 || true`,
          sessionId,
          false
        )
        isDirty = statusRes.stdout.trim().length > 0
      } catch {
        // ignore
      }

      return { isGit: true, branch: branch || 'HEAD', isDirty }
    } catch {
      return { isGit: false, branch: '', isDirty: false }
    }
  }

  public async getGitStatus(
    remotePath: string,
    sessionId?: string
  ): Promise<{
    isGit: boolean
    branch: string
    root: string
    files: { path: string; relPath: string; status: 'M' | 'A' | 'D' | 'U'; staged: boolean; isDirectory?: boolean }[]
  }> {
    const session = this.getSession(sessionId)
    if (!session || !session.isConnected) {
      return { isGit: false, branch: '', root: '', files: [] }
    }

    try {
      const cd = this.gitCd(remotePath)
      const infoCmd = `${cd} && git -c safe.directory=* rev-parse --show-toplevel 2>/dev/null && git -c safe.directory=* rev-parse --abbrev-ref HEAD 2>/dev/null || true`
      const infoRes = await this.execRemote(infoCmd, sessionId, false)
      const infoLines = infoRes.stdout.trim().split('\n').map((l) => l.trim()).filter(Boolean)
      if (infoLines.length < 2) {
        return { isGit: false, branch: '', root: '', files: [] }
      }

      const gitRoot = infoLines[0]
      const branch = infoLines[1]
      const escGitRoot = gitRoot.replace(/'/g, "'\\''")

      const statusCmd = `PATH=$PATH:/usr/local/bin:/usr/bin:/bin cd '${escGitRoot}' 2>/dev/null && git -c safe.directory=* -c status.showUntrackedFiles=normal status --porcelain=v1 -unormal 2>/dev/null || true`
      const statusRes = await this.execRemote(statusCmd, sessionId, false)
      const rawLines = statusRes.stdout.split('\n').filter(Boolean)

      const files: { path: string; relPath: string; status: 'M' | 'A' | 'D' | 'U'; staged: boolean; isDirectory?: boolean }[] = []

      for (const line of rawLines) {
        if (line.length < 3) continue
        const x = line[0]
        const y = line[1]
        let relPath = line.substring(3).trim()
        if (relPath.startsWith('"') && relPath.endsWith('"')) {
          relPath = relPath.slice(1, -1)
        }
        if (relPath.includes(' -> ')) {
          relPath = relPath.split(' -> ')[1].trim()
        }

        const isDirectory = relPath.endsWith('/')
        const cleanRelPath = relPath.replace(/\/+$/, '')

        let status: 'M' | 'A' | 'D' | 'U' = 'M'
        let staged = false

        if (x === '?' || y === '?') {
          status = 'U'
        } else if (x === 'D' || y === 'D') {
          status = 'D'
        } else if (x === 'A' || y === 'A') {
          status = 'A'
        } else {
          status = 'M'
        }

        if (x !== ' ' && x !== '?') {
          staged = true
        }

        const fullPath = `${gitRoot}/${cleanRelPath}`.replace(/\/+/g, '/')
        files.push({ path: fullPath, relPath: cleanRelPath, status, staged, isDirectory })
      }

      return { isGit: true, branch, root: gitRoot, files }
    } catch {
      return { isGit: false, branch: '', root: '', files: [] }
    }
  }

  public async gitCommit(
    remotePath: string,
    message: string,
    sessionId?: string
  ): Promise<{ success: boolean; message: string; commitHash?: string; shortHash?: string }> {
    const session = this.getSession(sessionId)
    if (!session || !session.isConnected) throw new Error('SFTP client is not connected.')
    const cd = this.gitCd(remotePath)
    const escMsg = message.replace(/'/g, "'\\''")
    const cmd = `${cd} && git -c safe.directory=* add -A && git -c safe.directory=* commit -m '${escMsg}' && git -c safe.directory=* rev-parse HEAD`
    let res = await this.execRemote(cmd, sessionId, false)
    if (res.code !== 0 && session.config?.password) {
      res = await this.execRemote(cmd, sessionId, true)
    }
    if (res.code !== 0) {
      throw new Error(res.stderr.trim() || res.stdout.trim() || 'Failed to commit.')
    }
    const lines = res.stdout.trim().split('\n').map((l) => l.trim()).filter(Boolean)
    const commitHash = lines[lines.length - 1] || ''
    const shortHash = commitHash.slice(0, 7)
    return { success: true, message: lines.slice(0, -1).join('\n') || 'Committed successfully.', commitHash, shortHash }
  }

  public async gitDiscard(
    filePath: string,
    sessionId?: string
  ): Promise<void> {
    const session = this.getSession(sessionId)
    if (!session || !session.isConnected) throw new Error('SFTP client is not connected.')
    const cleanPath = (filePath || '').replace(/^diff:/, '').replace(/\/+/g, '/').replace(/\/+$/, '')
    const dir = path.posix.dirname(cleanPath)
    const base = path.posix.basename(cleanPath)
    const escBase = base.replace(/'/g, "'\\''")
    const escClean = cleanPath.replace(/'/g, "'\\''")
    const cmd = `${this.gitCd(dir)} && (git -c safe.directory=* restore -- '${escClean}' 2>/dev/null || git -c safe.directory=* restore -- '${escBase}' 2>/dev/null || git -c safe.directory=* checkout -- '${escClean}' 2>/dev/null || git -c safe.directory=* checkout -- '${escBase}' 2>/dev/null || git -c safe.directory=* clean -fd -- '${escClean}' 2>/dev/null || git -c safe.directory=* clean -fd -- '${escBase}' 2>/dev/null || rm -rf '${escClean}')`
    await this.execRemote(cmd, sessionId, false)
  }

  public async gitStage(
    filePath: string,
    staged: boolean,
    sessionId?: string
  ): Promise<void> {
    const session = this.getSession(sessionId)
    if (!session || !session.isConnected) throw new Error('SFTP client is not connected.')
    const cleanPath = (filePath || '').replace(/^diff:/, '').replace(/\/+/g, '/').replace(/\/+$/, '')
    const dir = path.posix.dirname(cleanPath)
    const base = path.posix.basename(cleanPath)
    const escBase = base.replace(/'/g, "'\\''")
    const escClean = cleanPath.replace(/'/g, "'\\''")

    const action = staged
      ? `git -c safe.directory=* add -A -- '${escBase}' 2>/dev/null || git -c safe.directory=* add -A -- '${escClean}'`
      : `git -c safe.directory=* restore --staged -- '${escBase}' 2>/dev/null || git -c safe.directory=* restore --staged -- '${escClean}' 2>/dev/null || git -c safe.directory=* reset HEAD -- '${escBase}' 2>/dev/null || git -c safe.directory=* reset HEAD -- '${escClean}' 2>/dev/null || git -c safe.directory=* rm --cached -r -f -- '${escBase}' 2>/dev/null || git -c safe.directory=* rm --cached -r -f -- '${escClean}' 2>/dev/null`

    const cmd = `${this.gitCd(dir)} && ${action}`
    let res = await this.execRemote(cmd, sessionId, false)
    if (res.code !== 0 && session.config?.password) {
      res = await this.execRemote(cmd, sessionId, true)
    }
    if (res.code !== 0) {
      throw new Error(res.stderr.trim() || res.stdout.trim() || `Failed to ${staged ? 'stage' : 'unstage'} file.`)
    }
  }

  public async gitStageAll(remotePath: string, sessionId?: string): Promise<void> {
    const session = this.getSession(sessionId)
    if (!session || !session.isConnected) throw new Error('SFTP client is not connected.')
    const cmd = `${this.gitCd(remotePath)} && git -c safe.directory=* add -A`
    let res = await this.execRemote(cmd, sessionId, false)
    if (res.code !== 0 && session.config?.password) {
      res = await this.execRemote(cmd, sessionId, true)
    }
    if (res.code !== 0) {
      throw new Error(res.stderr.trim() || res.stdout.trim() || 'Failed to stage all changes.')
    }
  }

  public async gitDiscardAll(remotePath: string, sessionId?: string): Promise<void> {
    await this.execRemote(`${this.gitCd(remotePath)} && git -c safe.directory=* checkout -- . && git -c safe.directory=* clean -fd`, sessionId, false)
  }

  public async gitPull(remotePath: string, sessionId?: string): Promise<{ success: boolean; message: string }> {
    const res = await this.execRemote(`${this.gitCd(remotePath)} && git -c safe.directory=* pull`, sessionId, false)
    return { success: true, message: res.stdout.trim() || res.stderr.trim() || 'Pulled.' }
  }

  public async gitPush(remotePath: string, sessionId?: string): Promise<{ success: boolean; message: string }> {
    const session = this.getSession(sessionId)
    if (!session || !session.isConnected) throw new Error('SFTP client is not connected.')
    const cmd = `${this.gitCd(remotePath)} && git -c safe.directory=* push`
    let res = await this.execRemote(cmd, sessionId, false)
    if (res.code !== 0 && session.config?.password) {
      res = await this.execRemote(cmd, sessionId, true)
    }
    return { success: res.code === 0, message: res.stdout.trim() || res.stderr.trim() || 'Pushed.' }
  }

  public async gitCherryPick(
    remotePath: string,
    hash: string,
    options?: { autoPush?: boolean },
    sessionId?: string
  ): Promise<{ success: boolean; message: string; isConflict?: boolean }> {
    const session = this.getSession(sessionId)
    if (!session || !session.isConnected) throw new Error('SFTP client is not connected.')
    const cleanHash = (hash || '').trim().replace(/[^a-f0-9]/gi, '')
    if (!cleanHash) throw new Error('Invalid commit hash.')

    const cd = this.gitCd(remotePath)
    await this.execRemote(`${cd} && git -c safe.directory=* fetch --all 2>/dev/null || true`, sessionId, false)

    const pickCmd = `${cd} && git -c safe.directory=* cherry-pick '${cleanHash}'`
    let res = await this.execRemote(pickCmd, sessionId, false)
    if (res.code !== 0 && session.config?.password) {
      res = await this.execRemote(pickCmd, sessionId, true)
    }
    if (res.code !== 0) {
      const errOut = (res.stderr || res.stdout || '').trim()
      const isConflict = errOut.toLowerCase().includes('conflict') || errOut.toLowerCase().includes('could not apply')
      return { success: false, message: errOut || 'Cherry-pick failed.', isConflict }
    }

    let pushMsg = ''
    if (options?.autoPush) {
      const pushCmd = `${cd} && git -c safe.directory=* push`
      let pushRes = await this.execRemote(pushCmd, sessionId, false)
      if (pushRes.code !== 0 && session.config?.password) {
        pushRes = await this.execRemote(pushCmd, sessionId, true)
      }
      if (pushRes.code !== 0) {
        pushMsg = ` (Push warning: ${(pushRes.stderr || pushRes.stdout).trim()})`
      } else {
        pushMsg = ' and pushed to remote.'
      }
    }
    return { success: true, message: (res.stdout.trim() || `Cherry-picked ${cleanHash} successfully`) + pushMsg }
  }

  public async gitCherryPickAbort(remotePath: string, sessionId?: string): Promise<{ success: boolean; message: string }> {
    const session = this.getSession(sessionId)
    if (!session || !session.isConnected) throw new Error('SFTP client is not connected.')
    const res = await this.execRemote(`${this.gitCd(remotePath)} && git -c safe.directory=* cherry-pick --abort`, sessionId, false)
    return { success: res.code === 0, message: res.stdout.trim() || res.stderr.trim() || 'Aborted.' }
  }

  public async gitLog(remotePath: string, sessionId?: string): Promise<string> {
    const res = await this.execRemote(`${this.gitCd(remotePath)} && git -c safe.directory=* log --graph --oneline --decorate -n 35 2>/dev/null || true`, sessionId, false)
    return res.stdout.trim() || res.stderr.trim() || 'No git log available.'
  }

  public async getGitGraphCommits(remotePath: string, sessionId?: string, limit = 80): Promise<string> {
    const session = this.getSession(sessionId)
    if (!session || !session.isConnected) return ''
    const escDir = (remotePath || '').replace(/\/+/g, '/').replace(/'/g, "'\\''"), escCwd = (session.cwd || '').replace(/'/g, "'\\''")
    const cmd = `PATH=$PATH:/usr/local/bin:/usr/bin:/bin; for P in '${escDir}' '${escCwd}'; do [ -z "$P" ] && continue; T="$P"; [ -f "$T" ] && T=$(dirname "$T"); [ ! -d "$T" ] && continue; cd "$T" 2>/dev/null || continue; R=$(git -c safe.directory=* rev-parse --show-toplevel 2>/dev/null); if [ -n "$R" ]; then cd "$R" 2>/dev/null && git -c safe.directory=* log --all --date-order -n ${limit} --pretty=format:'%H%x09%h%x09%P%x09%an%x09%ae%x09%ar%x09%s%x09%D' 2>/dev/null || git -c safe.directory=* log -n ${limit} --pretty=format:'%H%x09%h%x09%P%x09%an%x09%ae%x09%ar%x09%s%x09%D' 2>/dev/null; exit 0; fi; done`
    const res = await this.execRemote(cmd, sessionId, false)
    return res.stdout.trim()
  }

  public async getCommitDetails(remotePath: string, hash: string, sessionId?: string): Promise<string> {
    const session = this.getSession(sessionId)
    if (!session || !session.isConnected) return ''
    const escDir = (remotePath || '').replace(/\/+/g, '/').replace(/'/g, "'\\''"), escCwd = (session.cwd || '').replace(/'/g, "'\\''"), escHash = hash.replace(/'/g, "'\\''")
    const cmd = `PATH=$PATH:/usr/local/bin:/usr/bin:/bin; for P in '${escDir}' '${escCwd}'; do [ -z "$P" ] && continue; T="$P"; [ -f "$T" ] && T=$(dirname "$T"); [ ! -d "$T" ] && continue; cd "$T" 2>/dev/null || continue; R=$(git -c safe.directory=* rev-parse --show-toplevel 2>/dev/null); if [ -n "$R" ]; then cd "$R" 2>/dev/null && git -c safe.directory=* show --stat --name-status -n 1 '${escHash}' 2>/dev/null; exit 0; fi; done`
    const res = await this.execRemote(cmd, sessionId, false)
    return res.stdout.trim()
  }

  public async getGitFileDiff(
    remotePath: string, hash: string, filePath: string, sessionId?: string
  ): Promise<{ diff: string; original: string; modified: string }> {
    const session = this.getSession(sessionId)
    if (!session || !session.isConnected) return { diff: '', original: '', modified: '' }
    const escDir = (remotePath || '').replace(/^diff:/, '').replace(/\/+/g, '/').replace(/'/g, "'\\''")
    const escCwd = (session.cwd || '').replace(/'/g, "'\\''")
    const escFile = (filePath || '').replace(/^diff:/, '').replace(/\/+/g, '/').replace(/'/g, "'\\''")
    const isCommit = hash && !['HEAD', 'working', 'staged', 'current'].includes(hash) && /^[a-f0-9]{4,40}$/i.test(hash)
    const escHash = isCommit ? hash.replace(/[^a-f0-9]/gi, '') : ''

    const cmd = `PATH=$PATH:/usr/local/bin:/usr/bin:/bin; FILE='${escFile}'; R=""
for P in '${escDir}' '${escCwd}' "$(dirname "$FILE")"; do
  [ -z "$P" ] && continue; T="$P"; [ -f "$T" ] && T=$(dirname "$T"); [ ! -d "$T" ] && continue
  cd "$T" 2>/dev/null || continue; R=$(git -c safe.directory=* rev-parse --show-toplevel 2>/dev/null); [ -n "$R" ] && break
done
if [ -n "$R" ]; then
  cd "$R" 2>/dev/null; REL="$FILE"
  case "$FILE" in "$R"/*) REL="\${FILE#$R/}" ;; esac
  REL="\${REL#/}"
  ${isCommit
    ? `D=$(git -c safe.directory=* diff '${escHash}~1' '${escHash}' -- "$REL" 2>/dev/null || git -c safe.directory=* show --format="" '${escHash}' -- "$REL" 2>/dev/null)
  O=$(git -c safe.directory=* show '${escHash}~1:'"$REL" 2>/dev/null || echo "")
  M=$(git -c safe.directory=* show '${escHash}:'"$REL" 2>/dev/null || echo "")`
    : `D=$(git -c safe.directory=* diff HEAD -- "$REL" 2>/dev/null || git -c safe.directory=* diff -- "$REL" 2>/dev/null)
  [ -z "$D" ] && [ -f "$REL" ] && D=$(git -c safe.directory=* diff --no-index /dev/null "$REL" 2>/dev/null)
  O=$(git -c safe.directory=* show HEAD:"$REL" 2>/dev/null || echo "")
  M=$([ -f "$REL" ] && cat "$REL" 2>/dev/null || cat "$R/$REL" 2>/dev/null || cat "$FILE" 2>/dev/null || echo "")`}
  printf "%s\\n___PULLMAN_DIFF_SEP___\\n%s\\n___PULLMAN_DIFF_SEP___\\n%s" "$D" "$O" "$M"
fi`

    try {
      const res = await this.execRemote(cmd, sessionId, false)
      const p = res.stdout.split('___PULLMAN_DIFF_SEP___')
      if (p.length >= 3) return { diff: p[0].trim(), original: p[1].replace(/^\n+|\n+$/g, ''), modified: p[2].replace(/^\n+|\n+$/g, '') }
      return { diff: res.stdout.trim(), original: '', modified: '' }
    } catch {
      return { diff: '', original: '', modified: '' }
    }
  }

  public async searchRemote(
    query: string,
    rootPath: string,
    sessionId?: string,
    options?: { isCaseSensitive?: boolean; isWholeWord?: boolean; isRegex?: boolean }
  ): Promise<{ file: string; line: number; text: string }[]> {
    const session = this.getSession(sessionId)
    if (!session || !session.isConnected) {
      throw new Error('SFTP client is not connected.')
    }
    const trimmed = query.trim()
    if (!trimmed) return []

    try {
      const cleanRoot = (rootPath || '/').replace(/\/+/g, '/')
      const escRoot = cleanRoot.replace(/'/g, "'\\''")
      const escQuery = trimmed.replace(/'/g, "'\\''")

      // Flag determination: default to -F (Fixed literal strings) so PHP symbols ($var, ->, ()) match accurately
      let flags = '-rn'
      if (!options?.isCaseSensitive) flags += 'i'
      if (options?.isWholeWord) flags += 'w'
      if (options?.isRegex) {
        flags += 'E'
      } else {
        flags += 'F'
      }

      const cmd = `cd '${escRoot}' 2>/dev/null && grep ${flags} -I --exclude-dir=.git -m 50 -- '${escQuery}' . 2>/dev/null | head -n 300 || true`
      const res = await this.execRemote(cmd, sessionId, false)
      const lines = res.stdout.split('\n').filter(Boolean)
      const results: { file: string; line: number; text: string }[] = []

      for (const rawLine of lines) {
        const firstColon = rawLine.indexOf(':')
        if (firstColon === -1) continue
        const secondColon = rawLine.indexOf(':', firstColon + 1)
        if (secondColon === -1) continue

        let relFile = rawLine.substring(0, firstColon)
        if (relFile.startsWith('./')) relFile = relFile.substring(2)
        const line = parseInt(rawLine.substring(firstColon + 1, secondColon), 10) || 1
        const text = rawLine.substring(secondColon + 1).trim()
        const fullPath = cleanRoot === '/' ? `/${relFile}` : `${cleanRoot}/${relFile}`

        results.push({ file: fullPath, line, text })
      }

      return results
    } catch {
      return []
    }
  }

  public async getGitBlame(
    filePath: string,
    line: number,
    sessionId?: string
  ): Promise<{ author: string; timeAgo: string; summary: string; hash: string; isUncommitted: boolean } | null> {
    const session = this.getSession(sessionId)
    if (!session || !session.isConnected || line <= 0) {
      return null
    }

    try {
      const cleanPath = (filePath || '').replace(/\/+/g, '/')
      const dir = path.posix.dirname(cleanPath)
      const baseName = path.posix.basename(cleanPath)
      const escDir = dir.replace(/'/g, "'\\''")
      const escFile = baseName.replace(/'/g, "'\\''")

      const cmd = `PATH=$PATH:/usr/local/bin:/usr/bin:/bin cd '${escDir}' 2>/dev/null && git -c safe.directory=* blame -L ${line},${line} --porcelain -- '${escFile}' 2>/dev/null || true`
      const res = await this.execRemote(cmd, sessionId, false)
      const output = res.stdout.trim()
      if (!output) {
        // Fallback: check if directory is inside git repo to detect uncommitted/new line
        try {
          const checkGit = await this.execRemote(
            `PATH=$PATH:/usr/local/bin:/usr/bin:/bin cd '${escDir}' 2>/dev/null && git -c safe.directory=* rev-parse --is-inside-work-tree 2>/dev/null || true`,
            sessionId,
            false
          )
          if (checkGit.stdout.trim().includes('true')) {
            return {
              author: 'You',
              timeAgo: 'now',
              summary: 'Uncommitted changes',
              hash: 'dirty',
              isUncommitted: true
            }
          }
        } catch {
          // ignore
        }
        return null
      }

      const lines = output.split('\n')
      const firstLine = lines[0] || ''
      const hash = firstLine.split(' ')[0]?.substring(0, 7) || ''

      let author = 'Not Committed Yet'
      let authorTime = 0
      let summary = 'Uncommitted changes'

      for (const l of lines) {
        if (l.startsWith('author ')) {
          author = l.substring(7).trim()
        } else if (l.startsWith('author-time ')) {
          authorTime = parseInt(l.substring(12).trim(), 10) * 1000
        } else if (l.startsWith('summary ')) {
          summary = l.substring(8).trim()
        }
      }

      const isUncommitted = hash.startsWith('0000000') || author === 'Not Committed Yet'

      let timeAgo = 'recently'
      if (!isUncommitted && authorTime > 0) {
        const m = Math.floor((Date.now() - authorTime) / 60000), h = Math.floor(m / 60), d = Math.floor(h / 24)
        if (d >= 365) timeAgo = `${Math.floor(d / 365)}y ago`
        else if (d >= 30) timeAgo = `${Math.floor(d / 30)}mo ago`
        else if (d > 0) timeAgo = `${d}d ago`
        else if (h > 0) timeAgo = `${h}h ago`
        else timeAgo = m > 0 ? `${m}m ago` : 'just now'
      }

      return {
        author: isUncommitted ? 'You' : author,
        timeAgo: isUncommitted ? 'now' : timeAgo,
        summary: isUncommitted ? 'Uncommitted changes' : summary,
        hash: isUncommitted ? 'dirty' : hash,
        isUncommitted
      }
    } catch {
      return null
    }
  }
}

export const sftpService = new SftpService()

