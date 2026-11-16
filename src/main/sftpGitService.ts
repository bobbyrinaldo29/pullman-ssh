<<<<<<< HEAD
import * as path from 'path'
import type { SftpService } from './sftpService'
import {
  GitCredentials,
  isGitAuthError,
  wrapCommandWithAskpass,
  getRemoteUrlCommand,
  buildSaveCredentialCommand,
  buildCherryPickCmd,
  buildGitGraphCommitsCmd,
  buildCommitDetailsCmd,
  buildGitFileDiffCmd,
  gitCd,
  buildAuthUrl,
  buildGitPullCommand,
  buildGitPushCommand
} from './sftpGitAuthHelper'

export class SftpGitService {
  private sftp: SftpService

  constructor(sftp: SftpService) {
    this.sftp = sftp
=======
import path from 'path'
import { sftpService } from './sftpService'

export class SftpGitService {
  public gitCd(remotePath: string): string {
    const clean = (remotePath || '/').replace(/^diff:/, '').replace(/\/+/g, '/')
    const esc = clean.replace(/'/g, "'\\''")
    return `PATH=$PATH:/usr/local/bin:/usr/bin:/bin; P='${esc}'; if [ -d "$P" ]; then cd "$P" 2>/dev/null; else cd "$(dirname "$P")" 2>/dev/null; fi`
>>>>>>> f2381c43715b37d1abf9d83d8794c3f9c9ac827e
  }

  public async getGitInfo(
    remotePath: string,
    sessionId?: string
  ): Promise<{ isGit: boolean; branch: string; isDirty: boolean }> {
<<<<<<< HEAD
    const session = this.sftp.getSession(sessionId)
    if (!session?.isConnected) return { isGit: false, branch: '', isDirty: false }
    try {
      const cd = gitCd(remotePath)
      const cmd = `${cd} && if [ "$(git -c safe.directory=* rev-parse --is-inside-work-tree 2>/dev/null)" = "true" ]; then echo "GIT_YES"; git -c safe.directory=* rev-parse --abbrev-ref HEAD 2>/dev/null || echo "HEAD"; git -c safe.directory=* status --porcelain 2>/dev/null | head -n 1; else echo "GIT_NO"; fi`
      const res = await this.sftp.execRemote(cmd, sessionId, false)
      const lines = res.stdout.trim().split('\n').map((l) => l.trim())
      if (lines[0] !== 'GIT_YES') return { isGit: false, branch: '', isDirty: false }
      const branch = lines[1] || 'HEAD'
      const isDirty = Boolean(lines[2] && lines[2].length > 0)
      return { isGit: true, branch, isDirty }
=======
    const session = sftpService.getSession(sessionId)
    if (!session?.isConnected) return { isGit: false, branch: '', isDirty: false }
    try {
      const cd = this.gitCd(remotePath)
      const res = await sftpService.execRemote(
        `${cd} && git -c safe.directory=* rev-parse --is-inside-work-tree 2>/dev/null && git -c safe.directory=* rev-parse --abbrev-ref HEAD 2>/dev/null || true`,
        sessionId,
        false
      )
      const lines = res.stdout.trim().split('\n').map((l) => l.trim()).filter(Boolean)
      if (lines.length === 0) return { isGit: false, branch: '', isDirty: false }
      const isInside = lines.includes('true'), branch = lines.find((l) => l !== 'true') || ''
      if (!isInside && !branch) return { isGit: false, branch: '', isDirty: false }

      let isDirty = false
      try {
        const statusRes = await sftpService.execRemote(
          `${cd} && git -c safe.directory=* status --porcelain 2>/dev/null | head -n 1 || true`,
          sessionId,
          false
        )
        isDirty = statusRes.stdout.trim().length > 0
      } catch {
        // ignore
      }

      return { isGit: true, branch: branch || 'HEAD', isDirty }
>>>>>>> f2381c43715b37d1abf9d83d8794c3f9c9ac827e
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
<<<<<<< HEAD
    const session = this.sftp.getSession(sessionId)
=======
    const session = sftpService.getSession(sessionId)
>>>>>>> f2381c43715b37d1abf9d83d8794c3f9c9ac827e
    if (!session || !session.isConnected) {
      return { isGit: false, branch: '', root: '', files: [] }
    }

    try {
<<<<<<< HEAD
      const cd = gitCd(remotePath)
      const combinedCmd = `${cd} && ROOT=$(git -c safe.directory=* rev-parse --show-toplevel 2>/dev/null); if [ -n "$ROOT" ]; then echo "PULLMAN_ROOT:$ROOT"; echo "PULLMAN_BRANCH:$(git -c safe.directory=* rev-parse --abbrev-ref HEAD 2>/dev/null || echo HEAD)"; echo "___STATUS_BEGIN___"; cd "$ROOT" 2>/dev/null && git -c safe.directory=* -c status.showUntrackedFiles=normal status --porcelain=v1 -unormal 2>/dev/null || true; else echo "PULLMAN_NOT_GIT"; fi`
      const res = await this.sftp.execRemote(combinedCmd, sessionId, false)
      const out = res.stdout
      if (out.includes('PULLMAN_NOT_GIT') || !out.includes('___STATUS_BEGIN___')) {
        return { isGit: false, branch: '', root: '', files: [] }
      }

      const [headerPart, statusPart = ''] = out.split('___STATUS_BEGIN___')
      const headerLines = headerPart.trim().split('\n')
      let gitRoot = ''
      let branch = 'HEAD'
      for (const line of headerLines) {
        if (line.startsWith('PULLMAN_ROOT:')) gitRoot = line.substring(13).trim()
        else if (line.startsWith('PULLMAN_BRANCH:')) branch = line.substring(15).trim()
      }

      if (!gitRoot) return { isGit: false, branch: '', root: '', files: [] }

      const rawLines = statusPart.split('\n').filter(Boolean)
=======
      const cd = this.gitCd(remotePath)
      const infoCmd = `${cd} && git -c safe.directory=* rev-parse --show-toplevel 2>/dev/null && git -c safe.directory=* rev-parse --abbrev-ref HEAD 2>/dev/null || true`
      const infoRes = await sftpService.execRemote(infoCmd, sessionId, false)
      const infoLines = infoRes.stdout.trim().split('\n').map((l) => l.trim()).filter(Boolean)
      if (infoLines.length < 2) {
        return { isGit: false, branch: '', root: '', files: [] }
      }

      const gitRoot = infoLines[0]
      const branch = infoLines[1]
      const escGitRoot = gitRoot.replace(/'/g, "'\\''")

      const statusCmd = `PATH=$PATH:/usr/local/bin:/usr/bin:/bin cd '${escGitRoot}' 2>/dev/null && git -c safe.directory=* -c status.showUntrackedFiles=normal status --porcelain=v1 -unormal 2>/dev/null || true`
      const statusRes = await sftpService.execRemote(statusCmd, sessionId, false)
      const rawLines = statusRes.stdout.split('\n').filter(Boolean)

>>>>>>> f2381c43715b37d1abf9d83d8794c3f9c9ac827e
      const files: { path: string; relPath: string; status: 'M' | 'A' | 'D' | 'U'; staged: boolean; isDirectory?: boolean }[] = []

      for (const line of rawLines) {
        if (line.length < 3) continue
        const x = line[0]
        const y = line[1]
        let relPath = line.substring(3).trim()
<<<<<<< HEAD
        if (relPath.startsWith('"') && relPath.endsWith('"')) {
          relPath = relPath.slice(1, -1)
        }
        if (relPath.includes(' -> ')) {
          relPath = relPath.split(' -> ')[1].trim()
        }
=======
        if (relPath.startsWith('"') && relPath.endsWith('"')) relPath = relPath.slice(1, -1)
        if (relPath.includes(' -> ')) relPath = relPath.split(' -> ')[1].trim()
>>>>>>> f2381c43715b37d1abf9d83d8794c3f9c9ac827e

        const isDirectory = relPath.endsWith('/')
        const cleanRelPath = relPath.replace(/\/+$/, '')

        let status: 'M' | 'A' | 'D' | 'U' = 'M'
        let staged = false

<<<<<<< HEAD
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
=======
        if (x === '?' || y === '?') status = 'U'
        else if (x === 'D' || y === 'D') status = 'D'
        else if (x === 'A' || y === 'A') status = 'A'
        else status = 'M'

        if (x !== ' ' && x !== '?') staged = true
>>>>>>> f2381c43715b37d1abf9d83d8794c3f9c9ac827e

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
<<<<<<< HEAD
    const session = this.sftp.getSession(sessionId)
    if (!session || !session.isConnected) throw new Error('SFTP client is not connected.')
    const cd = gitCd(remotePath)
    const escMsg = message.replace(/'/g, "'\\''")
    const cmd = `${cd} && if git -c safe.directory=* status --porcelain=v1 | grep -E '^[MADRC]' >/dev/null 2>&1; then :; else git -c safe.directory=* add -A; fi && git -c safe.directory=* commit -m '${escMsg}' && git -c safe.directory=* rev-parse HEAD`
    let res = await this.sftp.execRemote(cmd, sessionId, false)
    if (res.code !== 0 && session.config?.password) {
      res = await this.sftp.execRemote(cmd, sessionId, true)
    }
    if (res.code !== 0) {
      throw new Error(res.stderr.trim() || res.stdout.trim() || 'Failed to commit.')
    }
=======
    const session = sftpService.getSession(sessionId)
    if (!session || !session.isConnected) throw new Error('SFTP client is not connected.')
    const cd = this.gitCd(remotePath)
    const escMsg = message.replace(/'/g, "'\\''")
    const cmd = `${cd} && if git -c safe.directory=* status --porcelain=v1 | grep -E '^[MADRC]' >/dev/null 2>&1; then :; else git -c safe.directory=* add -A; fi && git -c safe.directory=* commit -m '${escMsg}' && git -c safe.directory=* rev-parse HEAD`
    let res = await sftpService.execRemote(cmd, sessionId, false)
    if (res.code !== 0 && session.config?.password) {
      res = await sftpService.execRemote(cmd, sessionId, true)
    }
    if (res.code !== 0) throw new Error(res.stderr.trim() || res.stdout.trim() || 'Failed to commit.')
>>>>>>> f2381c43715b37d1abf9d83d8794c3f9c9ac827e
    const lines = res.stdout.trim().split('\n').map((l) => l.trim()).filter(Boolean)
    const commitHash = lines[lines.length - 1] || ''
    const shortHash = commitHash.slice(0, 7)
    return { success: true, message: lines.slice(0, -1).join('\n') || 'Committed successfully.', commitHash, shortHash }
  }

<<<<<<< HEAD
  public async gitDiscard(
    filePath: string,
    sessionId?: string
  ): Promise<void> {
    const session = this.sftp.getSession(sessionId)
=======
  public async gitDiscard(filePath: string, sessionId?: string): Promise<void> {
    const session = sftpService.getSession(sessionId)
>>>>>>> f2381c43715b37d1abf9d83d8794c3f9c9ac827e
    if (!session || !session.isConnected) throw new Error('SFTP client is not connected.')
    const cleanPath = (filePath || '').replace(/^diff:/, '').replace(/\/+/g, '/').replace(/\/+$/, '')
    const dir = path.posix.dirname(cleanPath)
    const base = path.posix.basename(cleanPath)
    const escBase = base.replace(/'/g, "'\\''")
    const escClean = cleanPath.replace(/'/g, "'\\''")
<<<<<<< HEAD

    const cmd = `${gitCd(dir)} && (git -c safe.directory=* restore -- '${escClean}' 2>/dev/null || git -c safe.directory=* restore -- '${escBase}' 2>/dev/null || git -c safe.directory=* checkout -- '${escClean}' 2>/dev/null || git -c safe.directory=* checkout -- '${escBase}' 2>/dev/null || git -c safe.directory=* clean -fd -- '${escClean}' 2>/dev/null || git -c safe.directory=* clean -fd -- '${escBase}' 2>/dev/null || rm -rf '${escClean}')`
    const res = await this.sftp.execRemote(cmd, sessionId, false)
    if (res.code !== 0 && session.config?.password) {
      await this.sftp.execRemote(cmd, sessionId, true)
    }
  }

  public async gitStage(
    filePath: string,
    staged: boolean,
    sessionId?: string
  ): Promise<void> {
    const session = this.sftp.getSession(sessionId)
=======
    const cmd = `${this.gitCd(dir)} && (git -c safe.directory=* restore -- '${escClean}' 2>/dev/null || git -c safe.directory=* restore -- '${escBase}' 2>/dev/null || git -c safe.directory=* checkout -- '${escClean}' 2>/dev/null || git -c safe.directory=* checkout -- '${escBase}' 2>/dev/null || git -c safe.directory=* clean -fd -- '${escClean}' 2>/dev/null || git -c safe.directory=* clean -fd -- '${escBase}' 2>/dev/null || rm -rf '${escClean}')`
    const res = await sftpService.execRemote(cmd, sessionId, false)
    if (res.code !== 0 && session.config?.password) await sftpService.execRemote(cmd, sessionId, true)
  }

  public async gitStage(filePath: string, staged: boolean, sessionId?: string): Promise<void> {
    const session = sftpService.getSession(sessionId)
>>>>>>> f2381c43715b37d1abf9d83d8794c3f9c9ac827e
    if (!session || !session.isConnected) throw new Error('SFTP client is not connected.')
    const cleanPath = (filePath || '').replace(/^diff:/, '').replace(/\/+/g, '/').replace(/\/+$/, '')
    const dir = path.posix.dirname(cleanPath)
    const base = path.posix.basename(cleanPath)
    const escBase = base.replace(/'/g, "'\\''")
    const escClean = cleanPath.replace(/'/g, "'\\''")
<<<<<<< HEAD

=======
>>>>>>> f2381c43715b37d1abf9d83d8794c3f9c9ac827e
    const action = staged
      ? `git -c safe.directory=* add -A -- '${escBase}' 2>/dev/null || git -c safe.directory=* add -A -- '${escClean}'`
      : `git -c safe.directory=* restore --staged -- '${escBase}' 2>/dev/null || git -c safe.directory=* restore --staged -- '${escClean}' 2>/dev/null || git -c safe.directory=* reset HEAD -- '${escBase}' 2>/dev/null || git -c safe.directory=* reset HEAD -- '${escClean}' 2>/dev/null || git -c safe.directory=* rm --cached -r -f -- '${escBase}' 2>/dev/null || git -c safe.directory=* rm --cached -r -f -- '${escClean}' 2>/dev/null`

<<<<<<< HEAD
    const cmd = `${gitCd(dir)} && ${action}`
    let res = await this.sftp.execRemote(cmd, sessionId, false)
    if (res.code !== 0 && (session.config?.password || session.config?.user !== 'root')) {
      res = await this.sftp.execRemote(cmd, sessionId, true)
    }
    if (res.code !== 0) {
      throw new Error(res.stderr.trim() || res.stdout.trim() || `Failed to ${staged ? 'stage' : 'unstage'} file.`)
    }
  }

  public async gitStageAll(remotePath: string, sessionId?: string): Promise<void> {
    const session = this.sftp.getSession(sessionId)
    if (!session || !session.isConnected) throw new Error('SFTP client is not connected.')
    const cmd = `${gitCd(remotePath)} && git -c safe.directory=* add -A`
    let res = await this.sftp.execRemote(cmd, sessionId, false)
    if (res.code !== 0 && (session.config?.password || session.config?.user !== 'root')) {
      res = await this.sftp.execRemote(cmd, sessionId, true)
    }
    if (res.code !== 0) {
      throw new Error(res.stderr.trim() || res.stdout.trim() || 'Failed to stage all changes.')
    }
  }

  public async gitDiscardAll(remotePath: string, sessionId?: string): Promise<void> {
    const cmd = `${gitCd(remotePath)} && git -c safe.directory=* checkout -- . && git -c safe.directory=* clean -fd`
    const res = await this.sftp.execRemote(cmd, sessionId, false)
    if (res.code !== 0) {
      const session = this.sftp.getSession(sessionId)
      if (session?.config?.password || session?.config?.user !== 'root') await this.sftp.execRemote(cmd, sessionId, true)
    }
  }

  public async gitPull(
    remotePath: string,
    sessionId?: string,
    credentials?: GitCredentials
  ): Promise<{ success: boolean; message: string; authRequired?: boolean; remoteUrl?: string }> {
    const session = this.sftp.getSession(sessionId)
    if (!session || !session.isConnected) throw new Error('SFTP client is not connected.')
    const baseCmd = buildGitPullCommand(remotePath)
    const { cmd } = wrapCommandWithAskpass(baseCmd, credentials)
    let res = await this.sftp.execRemote(cmd, sessionId, false)
    let output = (res.stdout || res.stderr || '').trim()
    let isAuth = isGitAuthError(output)
    let remoteUrl: string | undefined

    if (!isAuth && res.code !== 0 && (output.toLowerCase().includes('permission denied') || output.toLowerCase().includes('eacces'))) {
      if (session.config?.password || session.config?.user !== 'root') {
        res = await this.sftp.execRemote(cmd, sessionId, true)
        output = (res.stdout || res.stderr || '').trim()
        isAuth = isGitAuthError(output)
      }
    }

    if (isAuth && credentials?.username && credentials?.password) {
      try {
        const urlRes = await this.sftp.execRemote(getRemoteUrlCommand(remotePath), sessionId, false)
        remoteUrl = urlRes.stdout.trim() || undefined
        if (remoteUrl) {
          const authUrl = buildAuthUrl(remoteUrl, credentials)
          if (authUrl) {
            const cd = gitCd(remotePath)
            const escAuthUrl = authUrl.replace(/'/g, "'\\''")
            const fallbackCmd = `${cd} && BR=$(git -c safe.directory=* rev-parse --abbrev-ref HEAD 2>/dev/null); git -c safe.directory=* pull '${escAuthUrl}' "$BR" 2>&1 || git -c safe.directory=* pull '${escAuthUrl}' 2>&1`
            const retryRes = await this.sftp.execRemote(fallbackCmd, sessionId, false)
            if (retryRes.code === 0) {
              res = retryRes
              output = (res.stdout || res.stderr || '').trim()
              isAuth = false
            }
          }
        }
      } catch {
        // fallback ignored
      }
    }

    if (isAuth || (res.code === 0 && credentials?.remember)) {
      if (!remoteUrl) {
        try {
          const urlRes = await this.sftp.execRemote(getRemoteUrlCommand(remotePath), sessionId, false)
          remoteUrl = urlRes.stdout.trim() || undefined
        } catch {}
      }
    }

    if (isAuth) {
      return {
        success: false,
        message: output || 'Authentication required.',
        authRequired: true,
        remoteUrl
      }
    }

    if (res.code === 0 && credentials?.remember && remoteUrl) {
      try {
        const saveCmd = buildSaveCredentialCommand(remotePath, remoteUrl, credentials)
        if (saveCmd) await this.sftp.execRemote(saveCmd, sessionId, false)
      } catch {}
    }

    return {
      success: res.code === 0,
      message: res.code === 0 ? (output || 'Pulled from remote successfully.') : (output || 'Pull failed.'),
      remoteUrl
    }
  }

  public async gitPush(
    remotePath: string,
    sessionId?: string,
    credentials?: GitCredentials
  ): Promise<{ success: boolean; message: string; authRequired?: boolean; remoteUrl?: string }> {
    const session = this.sftp.getSession(sessionId)
    if (!session || !session.isConnected) throw new Error('SFTP client is not connected.')
    const baseCmd = buildGitPushCommand(remotePath)
    const { cmd } = wrapCommandWithAskpass(baseCmd, credentials)
    let res = await this.sftp.execRemote(cmd, sessionId, false)
    let output = (res.stdout || res.stderr || '').trim()
    let isAuth = isGitAuthError(output)
    let remoteUrl: string | undefined

    if (!isAuth && res.code !== 0 && (output.toLowerCase().includes('permission denied') || output.toLowerCase().includes('eacces'))) {
      if (session.config?.password || session.config?.user !== 'root') {
        res = await this.sftp.execRemote(cmd, sessionId, true)
        output = (res.stdout || res.stderr || '').trim()
        isAuth = isGitAuthError(output)
      }
    }

    if (isAuth && credentials?.username && credentials?.password) {
      try {
        const urlRes = await this.sftp.execRemote(getRemoteUrlCommand(remotePath), sessionId, false)
        remoteUrl = urlRes.stdout.trim() || undefined
        if (remoteUrl) {
          const authUrl = buildAuthUrl(remoteUrl, credentials)
          if (authUrl) {
            const cd = gitCd(remotePath)
            const escAuthUrl = authUrl.replace(/'/g, "'\\''")
            const fallbackCmd = `${cd} && BR=$(git -c safe.directory=* rev-parse --abbrev-ref HEAD 2>/dev/null); git -c safe.directory=* push '${escAuthUrl}' "$BR" 2>&1 || git -c safe.directory=* push -u '${escAuthUrl}' "$BR" 2>&1`
            const retryRes = await this.sftp.execRemote(fallbackCmd, sessionId, false)
            if (retryRes.code === 0) {
              res = retryRes
              output = (res.stdout || res.stderr || '').trim()
              isAuth = false
            }
          }
        }
      } catch {
        // fallback ignored
      }
    }

    if (isAuth || (res.code === 0 && credentials?.remember)) {
      if (!remoteUrl) {
        try {
          const urlRes = await this.sftp.execRemote(getRemoteUrlCommand(remotePath), sessionId, false)
          remoteUrl = urlRes.stdout.trim() || undefined
        } catch {}
      }
    }

    if (isAuth) {
      return {
        success: false,
        message: output || 'Authentication required.',
        authRequired: true,
        remoteUrl
      }
    }

    if (res.code === 0 && credentials?.remember && remoteUrl) {
      try {
        const saveCmd = buildSaveCredentialCommand(remotePath, remoteUrl, credentials)
        if (saveCmd) await this.sftp.execRemote(saveCmd, sessionId, false)
      } catch {}
    }

    return {
      success: res.code === 0,
      message: res.code === 0 ? (output || 'Pushed to origin successfully.') : (output || 'Push failed.'),
      remoteUrl
    }
=======
    const cmd = `${this.gitCd(dir)} && ${action}`
    let res = await sftpService.execRemote(cmd, sessionId, false)
    if (res.code !== 0 && session.config?.password) res = await sftpService.execRemote(cmd, sessionId, true)
    if (res.code !== 0) throw new Error(res.stderr.trim() || res.stdout.trim() || `Failed to ${staged ? 'stage' : 'unstage'} file.`)
  }

  public async gitStageAll(remotePath: string, sessionId?: string): Promise<void> {
    const session = sftpService.getSession(sessionId)
    if (!session || !session.isConnected) throw new Error('SFTP client is not connected.')
    const cmd = `${this.gitCd(remotePath)} && git -c safe.directory=* add -A`
    let res = await sftpService.execRemote(cmd, sessionId, false)
    if (res.code !== 0 && session.config?.password) res = await sftpService.execRemote(cmd, sessionId, true)
    if (res.code !== 0) throw new Error(res.stderr.trim() || res.stdout.trim() || 'Failed to stage all changes.')
  }

  public async gitDiscardAll(remotePath: string, sessionId?: string): Promise<void> {
    const cmd = `${this.gitCd(remotePath)} && git -c safe.directory=* checkout -- . && git -c safe.directory=* clean -fd`
    const res = await sftpService.execRemote(cmd, sessionId, false)
    if (res.code !== 0) {
      const session = sftpService.getSession(sessionId)
      if (session?.config?.password) await sftpService.execRemote(cmd, sessionId, true)
    }
  }

  public async gitPull(remotePath: string, sessionId?: string): Promise<{ success: boolean; message: string }> {
    const cmd = `${this.gitCd(remotePath)} && git -c safe.directory=* pull`
    let res = await sftpService.execRemote(cmd, sessionId, false)
    if (res.code !== 0) {
      const session = sftpService.getSession(sessionId)
      if (session?.config?.password) res = await sftpService.execRemote(cmd, sessionId, true)
    }
    return { success: res.code === 0, message: res.stdout.trim() || res.stderr.trim() || 'Pulled.' }
  }

  public async gitPush(remotePath: string, sessionId?: string): Promise<{ success: boolean; message: string }> {
    const session = sftpService.getSession(sessionId)
    if (!session || !session.isConnected) throw new Error('SFTP client is not connected.')
    const cmd = `${this.gitCd(remotePath)} && git -c safe.directory=* push`
    let res = await sftpService.execRemote(cmd, sessionId, false)
    if (res.code !== 0 && session.config?.password) res = await sftpService.execRemote(cmd, sessionId, true)
    return { success: res.code === 0, message: res.stdout.trim() || res.stderr.trim() || 'Pushed.' }
>>>>>>> f2381c43715b37d1abf9d83d8794c3f9c9ac827e
  }

  public async gitCherryPick(
    remotePath: string,
    hash: string,
<<<<<<< HEAD
    options?: { autoPush?: boolean; credentials?: GitCredentials },
    sessionId?: string
  ): Promise<{
    success: boolean
    message: string
    isConflict?: boolean
    pushFailed?: boolean
    authRequired?: boolean
    remoteUrl?: string
  }> {
    const session = this.sftp.getSession(sessionId)
=======
    options?: { autoPush?: boolean },
    sessionId?: string
  ): Promise<{ success: boolean; message: string; isConflict?: boolean }> {
    const session = sftpService.getSession(sessionId)
>>>>>>> f2381c43715b37d1abf9d83d8794c3f9c9ac827e
    if (!session || !session.isConnected) throw new Error('SFTP client is not connected.')
    const cleanHash = (hash || '').trim().replace(/[^a-f0-9]/gi, '')
    if (!cleanHash) throw new Error('Invalid commit hash.')

<<<<<<< HEAD
    const cd = gitCd(remotePath)

    // 1. Ensure git knows about the commit hash (fetch from origin if missing)
    const checkCommitCmd = `${cd} && git -c safe.directory=* cat-file -e '${cleanHash}^{commit}' 2>/dev/null`
    let checkCommit = await this.sftp.execRemote(checkCommitCmd, sessionId, false)
    if (checkCommit.code !== 0 && (session.config?.password || session.config?.user !== 'root')) {
      checkCommit = await this.sftp.execRemote(checkCommitCmd, sessionId, true)
    }
    if (checkCommit.code !== 0) {
      const fetchBase = `${cd} && (git -c safe.directory=* fetch origin '${cleanHash}' 2>&1 || git -c safe.directory=* fetch origin '+refs/heads/*:refs/remotes/origin/*' 2>&1 || git -c safe.directory=* fetch --all 2>&1)`
      const { cmd: fetchCmd } = wrapCommandWithAskpass(fetchBase, options?.credentials)
      const fetchRes = await this.sftp.execRemote(fetchCmd, sessionId, false)
      if (fetchRes.code !== 0 && (session.config?.password || session.config?.user !== 'root')) {
        await this.sftp.execRemote(fetchCmd, sessionId, true)
      }
      checkCommit = await this.sftp.execRemote(checkCommitCmd, sessionId, false)
      if (checkCommit.code !== 0 && (session.config?.password || session.config?.user !== 'root')) {
        checkCommit = await this.sftp.execRemote(checkCommitCmd, sessionId, true)
      }
    }

    if (checkCommit.code !== 0) {
      return {
        success: false,
        message: `Commit ${cleanHash.slice(0, 7)} not found in this repository or remote origin. Make sure the commit was pushed to origin from the source branch first.`
      }
    }

    // 2. Perform cherry-pick with identity fallback
    const pickCmd = buildCherryPickCmd(cd, cleanHash)
    let res = await this.sftp.execRemote(pickCmd, sessionId, false)
    if (res.code !== 0 && (session.config?.password || session.config?.user !== 'root')) {
      res = await this.sftp.execRemote(pickCmd, sessionId, true)
    }

=======
    const cd = this.gitCd(remotePath)
    await sftpService.execRemote(`${cd} && git -c safe.directory=* fetch --all 2>/dev/null || true`, sessionId, false)

    const pickCmd = `${cd} && git -c safe.directory=* cherry-pick '${cleanHash}'`
    let res = await sftpService.execRemote(pickCmd, sessionId, false)
    if (res.code !== 0 && session.config?.password) res = await sftpService.execRemote(pickCmd, sessionId, true)
>>>>>>> f2381c43715b37d1abf9d83d8794c3f9c9ac827e
    if (res.code !== 0) {
      const errOut = (res.stderr || res.stdout || '').trim()
      const isConflict = errOut.toLowerCase().includes('conflict') || errOut.toLowerCase().includes('could not apply')
      return { success: false, message: errOut || 'Cherry-pick failed.', isConflict }
    }

<<<<<<< HEAD
    // 3. Handle Auto-Push if requested
    let pushMsg = ''
    let pushFailed = false
    let authRequired = false
    let remoteUrl: string | undefined

    if (options?.autoPush) {
      const pushRes = await this.gitPush(remotePath, sessionId, options?.credentials)
      if (!pushRes.success) {
        pushFailed = true
        authRequired = Boolean(pushRes.authRequired)
        remoteUrl = pushRes.remoteUrl
        pushMsg = ` (Push warning: ${pushRes.message})`
      } else {
        pushMsg = ' and pushed to remote.'
      }
    }

    return {
      success: true,
      message: (res.stdout.trim() || `Cherry-picked ${cleanHash.slice(0, 7)} successfully`) + pushMsg,
      pushFailed,
      authRequired,
      remoteUrl
    }
  }

  public async gitCherryPickAbort(remotePath: string, sessionId?: string): Promise<{ success: boolean; message: string }> {
    const session = this.sftp.getSession(sessionId)
    if (!session || !session.isConnected) throw new Error('SFTP client is not connected.')
    const res = await this.sftp.execRemote(`${gitCd(remotePath)} && git -c safe.directory=* cherry-pick --abort`, sessionId, false)
=======
    let pushMsg = ''
    if (options?.autoPush) {
      const pushCmd = `${cd} && git -c safe.directory=* push`
      let pushRes = await sftpService.execRemote(pushCmd, sessionId, false)
      if (pushRes.code !== 0 && session.config?.password) pushRes = await sftpService.execRemote(pushCmd, sessionId, true)
      if (pushRes.code !== 0) pushMsg = ` (Push warning: ${(pushRes.stderr || pushRes.stdout).trim()})`
      else pushMsg = ' and pushed to remote.'
    }
    return { success: true, message: (res.stdout.trim() || `Cherry-picked ${cleanHash} successfully`) + pushMsg }
  }

  public async gitCherryPickAbort(remotePath: string, sessionId?: string): Promise<{ success: boolean; message: string }> {
    const session = sftpService.getSession(sessionId)
    if (!session || !session.isConnected) throw new Error('SFTP client is not connected.')
    const res = await sftpService.execRemote(`${this.gitCd(remotePath)} && git -c safe.directory=* cherry-pick --abort`, sessionId, false)
>>>>>>> f2381c43715b37d1abf9d83d8794c3f9c9ac827e
    return { success: res.code === 0, message: res.stdout.trim() || res.stderr.trim() || 'Aborted.' }
  }

  public async gitLog(remotePath: string, sessionId?: string): Promise<string> {
<<<<<<< HEAD
    const res = await this.sftp.execRemote(`${gitCd(remotePath)} && git -c safe.directory=* log --graph --oneline --decorate -n 35 2>/dev/null || true`, sessionId, false)
=======
    const res = await sftpService.execRemote(`${this.gitCd(remotePath)} && git -c safe.directory=* log --graph --oneline --decorate -n 35 2>/dev/null || true`, sessionId, false)
>>>>>>> f2381c43715b37d1abf9d83d8794c3f9c9ac827e
    return res.stdout.trim() || res.stderr.trim() || 'No git log available.'
  }

  public async getGitGraphCommits(remotePath: string, sessionId?: string, limit = 80): Promise<string> {
<<<<<<< HEAD
    const session = this.sftp.getSession(sessionId)
    if (!session || !session.isConnected) return ''
    const cmd = buildGitGraphCommitsCmd(remotePath, session.cwd || '', limit)
    const res = await this.sftp.execRemote(cmd, sessionId, false)
=======
    const session = sftpService.getSession(sessionId)
    if (!session || !session.isConnected) return ''
    const escDir = (remotePath || '').replace(/\/+/g, '/').replace(/'/g, "'\\''"), escCwd = (session.cwd || '').replace(/'/g, "'\\''")
    const cmd = `PATH=$PATH:/usr/local/bin:/usr/bin:/bin; for P in '${escDir}' '${escCwd}'; do [ -z "$P" ] && continue; T="$P"; [ -f "$T" ] && T=$(dirname "$T"); [ ! -d "$T" ] && continue; cd "$T" 2>/dev/null || continue; R=$(git -c safe.directory=* rev-parse --show-toplevel 2>/dev/null); if [ -n "$R" ]; then cd "$R" 2>/dev/null && git -c safe.directory=* log --all --date-order -n ${limit} --pretty=format:'%H%x09%h%x09%P%x09%an%x09%ae%x09%ar%x09%s%x09%D' 2>/dev/null || git -c safe.directory=* log -n ${limit} --pretty=format:'%H%x09%h%x09%P%x09%an%x09%ae%x09%ar%x09%s%x09%D' 2>/dev/null; exit 0; fi; done`
    const res = await sftpService.execRemote(cmd, sessionId, false)
>>>>>>> f2381c43715b37d1abf9d83d8794c3f9c9ac827e
    return res.stdout.trim()
  }

  public async getCommitDetails(remotePath: string, hash: string, sessionId?: string): Promise<string> {
<<<<<<< HEAD
    const session = this.sftp.getSession(sessionId)
    if (!session || !session.isConnected) return ''
    const cleanHash = (hash || '').trim().replace(/[^a-f0-9]/gi, '')
    if (!cleanHash) return ''
    const cmd = buildCommitDetailsCmd(remotePath, cleanHash)
    let res = await this.sftp.execRemote(cmd, sessionId, false)
    if (!res.stdout.trim() && (session.config?.password || session.config?.user !== 'root')) {
      res = await this.sftp.execRemote(cmd, sessionId, true)
=======
    const session = sftpService.getSession(sessionId)
    if (!session || !session.isConnected) return ''
    const cleanHash = (hash || '').trim().replace(/[^a-f0-9]/gi, '')
    if (!cleanHash) return ''
    const cd = this.gitCd(remotePath)
    const escHash = cleanHash.replace(/'/g, "'\\''")
    const logCmd = `git -c safe.directory=* --no-pager log -1 --no-color --pretty=format:'%H%x09%h%x09%an%x09%ar%x09%s%x09%b___SEP___' --stat --name-status '${escHash}'`
    const cmd = `${cd} && OUT=$(${logCmd} 2>/dev/null || true); if [ -z "$OUT" ]; then git -c safe.directory=* fetch --all 2>/dev/null || true; OUT=$(${logCmd} 2>/dev/null || true); fi; echo "$OUT"`
    let res = await sftpService.execRemote(cmd, sessionId, false)
    if (!res.stdout.trim() && session.config?.password) {
      res = await sftpService.execRemote(cmd, sessionId, true)
>>>>>>> f2381c43715b37d1abf9d83d8794c3f9c9ac827e
    }
    return res.stdout.trim()
  }

  public async getGitFileDiff(
<<<<<<< HEAD
    remotePath: string, hash: string, filePath: string, sessionId?: string
  ): Promise<{ diff: string; original: string; modified: string }> {
    const session = this.sftp.getSession(sessionId)
    if (!session || !session.isConnected) return { diff: '', original: '', modified: '' }
    const cmd = buildGitFileDiffCmd(remotePath, session.cwd || '', hash, filePath)
    try {
      const res = await this.sftp.execRemote(cmd, sessionId, false)
=======
    remotePath: string,
    hash: string,
    filePath: string,
    sessionId?: string
  ): Promise<{ diff: string; original: string; modified: string }> {
    const session = sftpService.getSession(sessionId)
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
      const res = await sftpService.execRemote(cmd, sessionId, false)
>>>>>>> f2381c43715b37d1abf9d83d8794c3f9c9ac827e
      const p = res.stdout.split('___PULLMAN_DIFF_SEP___')
      if (p.length >= 3) return { diff: p[0].trim(), original: p[1].replace(/^\n+|\n+$/g, ''), modified: p[2].replace(/^\n+|\n+$/g, '') }
      return { diff: res.stdout.trim(), original: '', modified: '' }
    } catch {
      return { diff: '', original: '', modified: '' }
    }
  }
<<<<<<< HEAD
}
=======

  public async searchRemote(
    query: string,
    rootPath: string,
    sessionId?: string,
    options?: { isCaseSensitive?: boolean; isWholeWord?: boolean; isRegex?: boolean }
  ): Promise<{ file: string; line: number; text: string }[]> {
    const session = sftpService.getSession(sessionId)
    if (!session || !session.isConnected) throw new Error('SFTP client is not connected.')
    const trimmed = query.trim()
    if (!trimmed) return []

    try {
      const cleanRoot = (rootPath || '/').replace(/\/+/g, '/')
      const escRoot = cleanRoot.replace(/'/g, "'\\''")
      const escQuery = trimmed.replace(/'/g, "'\\''")

      let flags = '-rn'
      if (!options?.isCaseSensitive) flags += 'i'
      if (options?.isWholeWord) flags += 'w'
      if (options?.isRegex) flags += 'E'
      else flags += 'F'

      const cmd = `cd '${escRoot}' 2>/dev/null && grep ${flags} -I --exclude-dir=.git -m 50 -- '${escQuery}' . 2>/dev/null | head -n 300 || true`
      const res = await sftpService.execRemote(cmd, sessionId, false)
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
    const session = sftpService.getSession(sessionId)
    if (!session || !session.isConnected || line <= 0) return null

    try {
      const cleanPath = (filePath || '').replace(/\/+/g, '/')
      const dir = path.posix.dirname(cleanPath)
      const baseName = path.posix.basename(cleanPath)
      const escDir = dir.replace(/'/g, "'\\''")
      const escFile = baseName.replace(/'/g, "'\\''")

      const cmd = `PATH=$PATH:/usr/local/bin:/usr/bin:/bin cd '${escDir}' 2>/dev/null && git -c safe.directory=* blame -L ${line},${line} --porcelain -- '${escFile}' 2>/dev/null || true`
      const res = await sftpService.execRemote(cmd, sessionId, false)
      const output = res.stdout.trim()
      if (!output) {
        try {
          const checkGit = await sftpService.execRemote(
            `PATH=$PATH:/usr/local/bin:/usr/bin:/bin cd '${escDir}' 2>/dev/null && git -c safe.directory=* rev-parse --is-inside-work-tree 2>/dev/null || true`,
            sessionId,
            false
          )
          if (checkGit.stdout.trim().includes('true')) {
            return { author: 'You', timeAgo: 'now', summary: 'Uncommitted changes', hash: 'dirty', isUncommitted: true }
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
        if (l.startsWith('author ')) author = l.substring(7).trim()
        else if (l.startsWith('author-time ')) authorTime = parseInt(l.substring(12).trim(), 10) * 1000
        else if (l.startsWith('summary ')) summary = l.substring(8).trim()
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

export const sftpGitService = new SftpGitService()

>>>>>>> f2381c43715b37d1abf9d83d8794c3f9c9ac827e
