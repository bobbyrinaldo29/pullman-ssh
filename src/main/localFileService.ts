import { promises as fs } from 'fs'
import * as os from 'os'
import * as path from 'path'
import { exec } from 'child_process'
import { promisify } from 'util'

const execPromise = promisify(exec)

export interface LocalFileItem {
  name: string
  path: string
  isDirectory: boolean
  size: number
  modifyTime: number
  author?: string
}

export class LocalFileService {
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
          modifyTime: stat.mtimeMs,
          author: os.userInfo?.()?.username || ''
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

  public async renameLocal(oldPath: string, newPath: string, asSudo = false): Promise<void> {
    if (asSudo && process.platform === 'darwin') {
      try {
        const escOld = oldPath.replace(/"/g, '\\"')
        const escNew = newPath.replace(/"/g, '\\"')
        await execPromise(`osascript -e 'do shell script "mv \\"${escOld}\\" \\"${escNew}\\"" with administrator privileges'`)
        return
      } catch {
        // fallback to standard fs rename
      }
    }
    await fs.rename(oldPath, newPath)
  }

  public async mkdirLocal(dirPath: string, asSudo = false): Promise<void> {
    if (asSudo && process.platform === 'darwin') {
      try {
        const esc = dirPath.replace(/"/g, '\\"')
        await execPromise(`osascript -e 'do shell script "mkdir -p \\"${esc}\\"" with administrator privileges'`)
        return
      } catch {
        // fallback to standard fs mkdir
      }
    }
    await fs.mkdir(dirPath, { recursive: true })
  }

  public async deleteLocal(filePath: string, asSudo = false): Promise<void> {
    if (asSudo && process.platform === 'darwin') {
      try {
        const esc = filePath.replace(/"/g, '\\"')
        await execPromise(`osascript -e 'do shell script "rm -rf \\"${esc}\\"" with administrator privileges'`)
        return
      } catch {
        // fallback to standard fs rm
      }
    }
    await fs.rm(filePath, { recursive: true, force: true })
  }
}

export const localFileService = new LocalFileService()

