import * as path from 'path'
import type { SftpService } from './sftpService'
import {
  GitCredentials,
  isGitAuthError,
  isPushDelivered,
  extractPushedRef,
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
  }

  public async getGitInfo(
    remotePath: string,
    sessionId?: string
  ): Promise<{ isGit: boolean; branch: string; isDirty: boolean }> {
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
    const session = this.sftp.getSession(sessionId)
    if (!session || !session.isConnected) {
      return { isGit: false, branch: '', root: '', files: [] }
    }

    try {
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
    const session = this.sftp.getSession(sessionId)
    if (!session || !session.isConnected) throw new Error('SFTP client is not connected.')
    const cd = gitCd(remotePath)
    const escMsg = message.replace(/'/g, "'\\''")
    const cmd = `${cd} && if git -c safe.directory=* status --porcelain=v1 | grep -E '^[MADRC]' >/dev/null 2>&1; then :; else git -c safe.directory=* add -A; fi && git -c safe.directory=* commit -m '${escMsg}' && git -c safe.directory=* rev-parse HEAD`
    let res = await this.sftp.execRemote(cmd, sessionId, false)
    if (res.code !== 0 && (session.config?.password || session.config?.user !== 'root')) {
      const healCmd = `${cd} && { _GD=$(git -c safe.directory=* rev-parse --git-dir 2>/dev/null || echo ".git"); rm -f "$_GD"/*.lock 2>/dev/null || true; chmod -R a+rwX "$_GD" 2>/dev/null || true; }`
      await this.sftp.execRemote(healCmd, sessionId, true).catch(() => {})
      res = await this.sftp.execRemote(cmd, sessionId, true)
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
    const session = this.sftp.getSession(sessionId)
    if (!session || !session.isConnected) throw new Error('SFTP client is not connected.')
    const cleanPath = (filePath || '').replace(/^diff:/, '').replace(/\/+/g, '/').replace(/\/+$/, '')
    const dir = path.posix.dirname(cleanPath)
    const base = path.posix.basename(cleanPath)
    const escBase = base.replace(/'/g, "'\\''")
    const escClean = cleanPath.replace(/'/g, "'\\''")

    const cmd = `${gitCd(dir)} && (git -c safe.directory=* restore -- '${escClean}' 2>/dev/null || git -c safe.directory=* restore -- '${escBase}' 2>/dev/null || git -c safe.directory=* checkout -- '${escClean}' 2>/dev/null || git -c safe.directory=* checkout -- '${escBase}' 2>/dev/null || git -c safe.directory=* clean -fd -- '${escClean}' 2>/dev/null || git -c safe.directory=* clean -fd -- '${escBase}' 2>/dev/null || rm -rf '${escClean}')`
    const res = await this.sftp.execRemote(cmd, sessionId, false)
    if (res.code !== 0 && (session.config?.password || session.config?.user !== 'root')) {
      await this.sftp.execRemote(cmd, sessionId, true)
    }
  }

  private async execWithSudoLockRetry(
    targetPath: string,
    cmd: string,
    sessionId?: string
  ): Promise<{ stdout: string; stderr: string; code: number }> {
    const session = this.sftp.getSession(sessionId)
    let res = await this.sftp.execRemote(cmd, sessionId, false)
    if (res.code !== 0 && (session?.config?.password || session?.config?.user !== 'root')) {
      let sudoRes = await this.sftp.execRemote(cmd, sessionId, true)
      if (sudoRes.code !== 0) {
        const combined = `${sudoRes.stderr}\n${sudoRes.stdout}\n${res.stderr}\n${res.stdout}`.toLowerCase()
        if (combined.includes('index.lock')) {
          const unlockCmd = `${gitCd(targetPath)} && _GD=$(git -c safe.directory=* rev-parse --git-dir 2>/dev/null || echo ".git"); rm -f "$_GD"/index.lock 2>/dev/null || true`
          await this.sftp.execRemote(unlockCmd, sessionId, true).catch(() => {})
          sudoRes = await this.sftp.execRemote(cmd, sessionId, true)
        }
      }
      res = sudoRes
    }
    return res
  }

  public async gitStage(
    filePath: string,
    staged: boolean,
    sessionId?: string
  ): Promise<void> {
    const session = this.sftp.getSession(sessionId)
    if (!session || !session.isConnected) throw new Error('SFTP client is not connected.')
    const cleanPath = (filePath || '').replace(/^diff:/, '').replace(/\/+/g, '/').replace(/\/+$/, '')
    const dir = path.posix.dirname(cleanPath)
    const base = path.posix.basename(cleanPath)
    const escBase = base.replace(/'/g, "'\\''")
    const escClean = cleanPath.replace(/'/g, "'\\''")

    const action = staged
      ? `git -c safe.directory=* add -A -- '${escBase}' 2>/dev/null || git -c safe.directory=* add -A -- '${escClean}'`
      : `git -c safe.directory=* restore --staged -- '${escBase}' 2>/dev/null || git -c safe.directory=* restore --staged -- '${escClean}' 2>/dev/null || git -c safe.directory=* reset HEAD -- '${escBase}' 2>/dev/null || git -c safe.directory=* reset HEAD -- '${escClean}' 2>/dev/null || git -c safe.directory=* rm --cached -r -f -- '${escBase}' 2>/dev/null || git -c safe.directory=* rm --cached -r -f -- '${escClean}' 2>/dev/null`

    const cmd = `${gitCd(dir)} && ${action}`
    const res = await this.execWithSudoLockRetry(dir, cmd, sessionId)
    if (res.code !== 0) {
      throw new Error(res.stderr.trim() || res.stdout.trim() || `Failed to ${staged ? 'stage' : 'unstage'} file.`)
    }
  }

  public async gitStageAll(remotePath: string, sessionId?: string): Promise<void> {
    const session = this.sftp.getSession(sessionId)
    if (!session || !session.isConnected) throw new Error('SFTP client is not connected.')
    const cmd = `${gitCd(remotePath)} && git -c safe.directory=* add -A`
    const res = await this.execWithSudoLockRetry(remotePath, cmd, sessionId)
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

    const isLocalFsPermError = (out: string): boolean => {
      const lower = out.toLowerCase()
      if (
        lower.includes('(publickey') ||
        lower.includes('publickey') ||
        lower.includes('username for') ||
        lower.includes('password for') ||
        lower.includes('access rights') ||
        lower.includes('could not read') ||
        lower.includes('terminal prompts disabled')
      ) {
        return false
      }
      return (
        lower.includes('.git/') ||
        lower.includes('unable to create') ||
        lower.includes('cannot create directory') ||
        lower.includes('unable to write') ||
        lower.includes('cannot lock ref') ||
        lower.includes('permission denied') ||
        lower.includes('index.lock') ||
        lower.includes('fetch_head')
      )
    }

    if (!isAuth && res.code !== 0 && (isLocalFsPermError(output) || output.toLowerCase().includes('permission denied') || session.config?.user !== 'root')) {
      // Permission healing: remove stale locks and heal permissions directly via sudo su
      const healCmd = `${gitCd(remotePath)} && {
        _GD=$(git -c safe.directory=* rev-parse --git-dir 2>/dev/null || echo ".git");
        rm -f "$_GD"/*.lock "$_GD"/refs/*/*.lock "$_GD"/refs/*/*/*.lock 2>/dev/null || true;
        chmod -R a+rwX "$_GD" 2>/dev/null || true;
      }`
      await this.sftp.execRemote(healCmd, sessionId, true).catch(() => {})

      // Retry git pull as root via sudo su
      const retryRes = await this.sftp.execRemote(cmd, sessionId, true)
      const retryOutput = (retryRes.stdout || retryRes.stderr || '').trim()
      if (retryRes.code === 0) {
        res = retryRes
        output = retryOutput
        isAuth = false
      } else if (!isGitAuthError(retryOutput)) {
        res = retryRes
        output = retryOutput
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
            let retryRes = await this.sftp.execRemote(fallbackCmd, sessionId, false)
            if (retryRes.code !== 0 && (session.config?.password || session.config?.user !== 'root')) {
              retryRes = await this.sftp.execRemote(fallbackCmd, sessionId, true)
            }
            if (retryRes.code === 0) {
              res = retryRes
              output = (res.stdout || res.stderr || '').trim()
              isAuth = false
            } else {
              const retryOut = (retryRes.stderr || retryRes.stdout || '').trim()
              if (retryOut) {
                output = retryOut
                isAuth = isGitAuthError(output)
              }
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

    const isLocalFsPermError = (out: string): boolean => {
      const lower = out.toLowerCase()
      if (
        lower.includes('(publickey') ||
        lower.includes('publickey') ||
        lower.includes('username for') ||
        lower.includes('password for') ||
        lower.includes('access rights') ||
        lower.includes('could not read') ||
        lower.includes('terminal prompts disabled')
      ) {
        return false
      }
      return (
        lower.includes('.git/') ||
        lower.includes('unable to create') ||
        lower.includes('cannot create directory') ||
        lower.includes('unable to write') ||
        lower.includes('cannot lock ref') ||
        lower.includes('update_ref failed') ||
        lower.includes('permission denied') ||
        lower.includes('index.lock')
      )
    }

    // 1. Check if commits were delivered to the remote git server
    let delivered = isPushDelivered(output)

    // 2. If not delivered and there was a local FS permission/lock error, heal permissions and retry via sudo su
    if (!delivered && !isAuth && res.code !== 0 && (isLocalFsPermError(output) || output.toLowerCase().includes('permission denied') || session.config?.user !== 'root')) {
      const healCmd = `${gitCd(remotePath)} && {
        _GD=$(git -c safe.directory=* rev-parse --git-dir 2>/dev/null || echo ".git");
        rm -f "$_GD"/*.lock "$_GD"/refs/*/*.lock "$_GD"/refs/*/*/*.lock 2>/dev/null || true;
        chmod -R a+rwX "$_GD" 2>/dev/null || true;
      }`
      await this.sftp.execRemote(healCmd, sessionId, true).catch(() => {})

      // Retry git push as root via sudo su
      const retryRes = await this.sftp.execRemote(cmd, sessionId, true)
      const retryOutput = (retryRes.stdout || retryRes.stderr || '').trim()
      if (retryRes.code === 0 || isPushDelivered(retryOutput)) {
        res = retryRes
        output = retryOutput
        isAuth = false
        delivered = isPushDelivered(output)
      } else if (!isGitAuthError(retryOutput)) {
        res = retryRes
        output = retryOutput
        delivered = isPushDelivered(output)
      }
    }

    // 3. Fallback with direct credentials URL if authenticated error
    if (!delivered && isAuth && credentials?.username && credentials?.password) {
      try {
        const urlRes = await this.sftp.execRemote(getRemoteUrlCommand(remotePath), sessionId, false)
        remoteUrl = urlRes.stdout.trim() || undefined
        if (remoteUrl) {
          const authUrl = buildAuthUrl(remoteUrl, credentials)
          if (authUrl) {
            const cd = gitCd(remotePath)
            const escAuthUrl = authUrl.replace(/'/g, "'\\''")
            const fallbackCmd = `${cd} && BR=$(git -c safe.directory=* rev-parse --abbrev-ref HEAD 2>/dev/null); git -c safe.directory=* push '${escAuthUrl}' "$BR" 2>&1 || git -c safe.directory=* push -u '${escAuthUrl}' "$BR" 2>&1`
            let retryRes = await this.sftp.execRemote(fallbackCmd, sessionId, false)
            if (retryRes.code !== 0 && (session.config?.password || session.config?.user !== 'root')) {
              retryRes = await this.sftp.execRemote(fallbackCmd, sessionId, true)
            }
            const retryOut = (retryRes.stdout || retryRes.stderr || '').trim()
            if (retryRes.code === 0 || isPushDelivered(retryOut)) {
              res = retryRes
              output = retryOut
              isAuth = false
              delivered = true
            } else if (retryOut) {
              output = retryOut
              isAuth = isGitAuthError(output)
            }
          }
        }
      } catch {
        // fallback ignored
      }
    }

    // 4. Handle delivered push (success on remote server, even if local ref update failed)
    if (delivered || res.code === 0) {
      // Heal local tracking ref so Git Graph & status show the updated branch
      try {
        const pushedInfo = extractPushedRef(output)
        const branchToUpdate = pushedInfo?.branch || ''
        const commitTarget = pushedInfo?.commitHash || 'HEAD'
        const trackingRefCmd = `${gitCd(remotePath)} && {
          _GD=$(git -c safe.directory=* rev-parse --git-dir 2>/dev/null || echo ".git");
          BR="${branchToUpdate}"
          [ -z "$BR" ] && BR=$(git -c safe.directory=* rev-parse --abbrev-ref HEAD 2>/dev/null || echo "");
          REMOTE=$(git -c safe.directory=* remote 2>/dev/null | head -n 1 || echo "origin");
          if [ -n "$BR" ] && [ -d "$_GD" ]; then
            rm -f "$_GD/refs/remotes/$REMOTE/$BR.lock" 2>/dev/null || true;
            mkdir -p "$_GD/refs/remotes/$REMOTE" 2>/dev/null || true;
            git -c safe.directory=* update-ref "refs/remotes/$REMOTE/$BR" ${commitTarget} 2>/dev/null || true;
          fi;
        }`
        await this.sftp.execRemote(trackingRefCmd, sessionId, true).catch(() => {})
      } catch {}

      if (credentials?.remember) {
        if (!remoteUrl) {
          try {
            const urlRes = await this.sftp.execRemote(getRemoteUrlCommand(remotePath), sessionId, false)
            remoteUrl = urlRes.stdout.trim() || undefined
          } catch {}
        }
        if (remoteUrl) {
          try {
            const saveCmd = buildSaveCredentialCommand(remotePath, remoteUrl, credentials)
            if (saveCmd) await this.sftp.execRemote(saveCmd, sessionId, false)
          } catch {}
        }
      }

      return {
        success: true,
        message:
          output && !output.includes('cannot lock ref') && !output.includes('Permission denied')
            ? output
            : 'Pushed to origin successfully.',
        remoteUrl
      }
    }

    if (isAuth) {
      if (!remoteUrl) {
        try {
          const urlRes = await this.sftp.execRemote(getRemoteUrlCommand(remotePath), sessionId, false)
          remoteUrl = urlRes.stdout.trim() || undefined
        } catch {}
      }
      return {
        success: false,
        message: output || 'Authentication required.',
        authRequired: true,
        remoteUrl
      }
    }

    return {
      success: false,
      message: output || 'Push failed.',
      remoteUrl
    }
  }

  public async gitCherryPick(
    remotePath: string,
    hash: string,
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
    if (!session || !session.isConnected) throw new Error('SFTP client is not connected.')
    const cleanHash = (hash || '').trim().replace(/[^a-f0-9]/gi, '')
    if (!cleanHash) throw new Error('Invalid commit hash.')

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

    if (res.code !== 0) {
      const errOut = (res.stderr || res.stdout || '').trim()
      const isConflict = errOut.toLowerCase().includes('conflict') || errOut.toLowerCase().includes('could not apply')
      return { success: false, message: errOut || 'Cherry-pick failed.', isConflict }
    }

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
    return { success: res.code === 0, message: res.stdout.trim() || res.stderr.trim() || 'Aborted.' }
  }

  public async gitLog(remotePath: string, sessionId?: string): Promise<string> {
    const res = await this.sftp.execRemote(`${gitCd(remotePath)} && git -c safe.directory=* log --graph --oneline --decorate -n 35 2>/dev/null || true`, sessionId, false)
    return res.stdout.trim() || res.stderr.trim() || 'No git log available.'
  }

  public async getGitGraphCommits(remotePath: string, sessionId?: string, limit = 80): Promise<string> {
    const session = this.sftp.getSession(sessionId)
    if (!session || !session.isConnected) return ''
    const cmd = buildGitGraphCommitsCmd(remotePath, session.cwd || '', limit)
    const res = await this.sftp.execRemote(cmd, sessionId, false)
    return res.stdout.trim()
  }

  public async getCommitDetails(remotePath: string, hash: string, sessionId?: string): Promise<string> {
    const session = this.sftp.getSession(sessionId)
    if (!session || !session.isConnected) return ''
    const cleanHash = (hash || '').trim().replace(/[^a-f0-9]/gi, '')
    if (!cleanHash) return ''
    const cmd = buildCommitDetailsCmd(remotePath, cleanHash)
    let res = await this.sftp.execRemote(cmd, sessionId, false)
    if (!res.stdout.trim() && (session.config?.password || session.config?.user !== 'root')) {
      res = await this.sftp.execRemote(cmd, sessionId, true)
    }
    return res.stdout.trim()
  }

  public async getGitFileDiff(
    remotePath: string, hash: string, filePath: string, sessionId?: string
  ): Promise<{ diff: string; original: string; modified: string }> {
    const session = this.sftp.getSession(sessionId)
    if (!session || !session.isConnected) return { diff: '', original: '', modified: '' }
    const cmd = buildGitFileDiffCmd(remotePath, session.cwd || '', hash, filePath)
    try {
      const res = await this.sftp.execRemote(cmd, sessionId, false)
      const p = res.stdout.split('___PULLMAN_DIFF_SEP___')
      if (p.length >= 3) return { diff: p[0].trim(), original: p[1].replace(/^\n+|\n+$/g, ''), modified: p[2].replace(/^\n+|\n+$/g, '') }
      return { diff: res.stdout.trim(), original: '', modified: '' }
    } catch {
      return { diff: '', original: '', modified: '' }
    }
  }
}
