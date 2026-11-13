import * as path from 'path'
import type { SftpService } from './sftpService'

export class SftpSearchService {
  private sftpService: SftpService

  constructor(sftpService: SftpService) {
    this.sftpService = sftpService
  }

  public async searchRemote(
    query: string,
    rootPath: string,
    sessionId?: string,
    options?: { isCaseSensitive?: boolean; isWholeWord?: boolean; isRegex?: boolean }
  ): Promise<{ file: string; line: number; text: string }[]> {
    const session = this.sftpService.getSession(sessionId)
    if (!session || !session.isConnected) {
      throw new Error('SFTP client is not connected.')
    }
    const trimmed = query.trim()
    if (!trimmed) return []

    try {
      const cleanRoot = (rootPath || '/').replace(/\/+/g, '/')
      const escRoot = cleanRoot.replace(/'/g, "'\\''")
      const escQuery = trimmed.replace(/'/g, "'\\''")

      let flags = '-rn'
      if (!options?.isCaseSensitive) flags += 'i'
      if (options?.isWholeWord) flags += 'w'
      if (options?.isRegex) {
        flags += 'E'
      } else {
        flags += 'F'
      }

      const cmd = `cd '${escRoot}' 2>/dev/null && grep ${flags} -I --exclude-dir=.git -m 50 -- '${escQuery}' . 2>/dev/null | head -n 300 || true`
      const res = await this.sftpService.execRemote(cmd, sessionId, false)
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
    const session = this.sftpService.getSession(sessionId)
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
      const res = await this.sftpService.execRemote(cmd, sessionId, false)
      const output = res.stdout.trim()
      if (!output) {
        try {
          const checkGit = await this.sftpService.execRemote(
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
        const m = Math.floor((Date.now() - authorTime) / 60000)
        const h = Math.floor(m / 60)
        const d = Math.floor(h / 24)
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

