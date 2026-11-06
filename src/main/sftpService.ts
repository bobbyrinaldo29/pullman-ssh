import SftpClient from 'ssh2-sftp-client'
import { promises as fs } from 'fs'
import * as os from 'os'
import * as path from 'path'

export interface SftpFileItem {
  name: string
  path: string
  isDirectory: boolean
  size: number
  modifyTime: number
  permissions?: string
  type: string
}

export interface LocalFileItem {
  name: string
  path: string
  isDirectory: boolean
  size: number
  modifyTime: number
}

export class SftpService {
  private client: SftpClient | null = null
  private isConnected = false

  public getConnectedStatus(): boolean {
    return this.isConnected
  }

  public async connect(config: {
    host: string
    port: number
    user: string
    password?: string
    timeoutMs?: number
  }): Promise<{ success: boolean; message: string; cwd?: string }> {
    await this.disconnect()
    this.client = new SftpClient()

    try {
      await this.client.connect({
        host: config.host,
        port: config.port,
        username: config.user,
        password: config.password || undefined,
        readyTimeout: config.timeoutMs || 10000,
        // @ts-ignore
        hostVerifier: () => true
      })

      this.isConnected = true
      let cwd = '/'
      try {
        cwd = await this.client.cwd()
      } catch {
        cwd = '/'
      }

      return {
        success: true,
        message: `Connected to ${config.user}@${config.host}:${config.port}`,
        cwd: cwd || '/'
      }
    } catch (err: unknown) {
      this.isConnected = false
      const errMsg = err instanceof Error ? err.message : String(err)
      return {
        success: false,
        message: `SFTP Connection failed: ${errMsg}`
      }
    }
  }

  public async disconnect(): Promise<void> {
    if (this.client) {
      try {
        await this.client.end()
      } catch {
        // ignore
      }
      this.client = null
    }
    this.isConnected = false
  }

  public async listRemote(remotePath: string): Promise<SftpFileItem[]> {
    if (!this.client || !this.isConnected) {
      throw new Error('SFTP client is not connected.')
    }
    const rawList = await this.client.list(remotePath)
    const items: SftpFileItem[] = rawList.map((item) => {
      const isDir = item.type === 'd'
      const cleanRemotePath = remotePath.endsWith('/')
        ? remotePath.slice(0, -1)
        : remotePath
      const fullPath = `${cleanRemotePath}/${item.name}`

      return {
        name: item.name,
        path: fullPath,
        isDirectory: isDir,
        size: item.size || 0,
        modifyTime: item.modifyTime || 0,
        permissions: item.rights
          ? `${item.rights.user || ''}${item.rights.group || ''}${item.rights.other || ''}`
          : '',
        type: item.type
      }
    })

    return items.sort((a, b) => {
      if (a.isDirectory && !b.isDirectory) return -1
      if (!a.isDirectory && b.isDirectory) return 1
      return a.name.localeCompare(b.name)
    })
  }

  public async upload(localPath: string, remotePath: string): Promise<void> {
    if (!this.client || !this.isConnected) {
      throw new Error('SFTP client is not connected.')
    }
    await this.client.fastPut(localPath, remotePath)
  }

  public async download(remotePath: string, localPath: string): Promise<void> {
    if (!this.client || !this.isConnected) {
      throw new Error('SFTP client is not connected.')
    }
    await this.client.fastGet(remotePath, localPath)
  }

  public async mkdirRemote(remotePath: string): Promise<void> {
    if (!this.client || !this.isConnected) {
      throw new Error('SFTP client is not connected.')
    }
    await this.client.mkdir(remotePath, true)
  }

  public async deleteRemote(remotePath: string, isDirectory = false): Promise<void> {
    if (!this.client || !this.isConnected) {
      throw new Error('SFTP client is not connected.')
    }
    if (isDirectory) {
      await this.client.rmdir(remotePath, true)
    } else {
      await this.client.delete(remotePath)
    }
  }

  public async renameRemote(oldPath: string, newPath: string): Promise<void> {
    if (!this.client || !this.isConnected) {
      throw new Error('SFTP client is not connected.')
    }
    await this.client.rename(oldPath, newPath)
  }

  // Local filesystem operations
  public getLocalHome(): string {
    return os.homedir()
  }

  public async listLocal(dirPath: string): Promise<LocalFileItem[]> {
    const targetDir = dirPath || os.homedir()
    const entries = await fs.readdir(targetDir, { withFileTypes: true })
    const items: LocalFileItem[] = []

    for (const e of entries) {
      try {
        const full = path.join(targetDir, e.name)
        const stat = await fs.stat(full)
        items.push({
          name: e.name,
          path: full,
          isDirectory: e.isDirectory(),
          size: stat.size,
          modifyTime: stat.mtimeMs
        })
      } catch {
        // ignore unreadable
      }
    }

    return items.sort((a, b) => {
      if (a.isDirectory && !b.isDirectory) return -1
      if (!a.isDirectory && b.isDirectory) return 1
      return a.name.localeCompare(b.name)
    })
  }

  public async mkdirLocal(dirPath: string): Promise<void> {
    await fs.mkdir(dirPath, { recursive: true })
  }

  public async deleteLocal(filePath: string): Promise<void> {
    await fs.rm(filePath, { recursive: true, force: true })
  }
}

export const sftpService = new SftpService()

