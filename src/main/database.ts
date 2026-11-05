import Database from 'better-sqlite3'
import { app } from 'electron'
import { join } from 'path'
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'fs'
import { randomBytes, createCipheriv, createDecipheriv } from 'crypto'

export interface ConnectionRecord {
  id: number
  name: string
  url?: string
  type: string
  color: string
  group: string
  host: string
  port: number
  user: string
  password?: string
  savePassword: boolean
  database?: string
  notes?: string
  remotePath?: string
  branch?: string
  status: string
  statusType: 'success' | 'warning' | 'error' | 'idle'
  createdAt?: string
  updatedAt?: string
}

export interface ConnectionInput {
  name: string
  url?: string
  type?: string
  color?: string
  group?: string
  host: string
  port: number
  user: string
  password?: string
  savePassword?: boolean
  database?: string
  notes?: string
  remotePath?: string
  branch?: string
}

class DatabaseService {
  private db: Database.Database | null = null
  private encryptionKey: Buffer | null = null

  public init(): void {
    const userDataPath = app?.getPath ? app.getPath('userData') : process.cwd()
    if (!existsSync(userDataPath)) {
      mkdirSync(userDataPath, { recursive: true })
    }

    // 1. Initialize Encryption Key (.master.key)
    this.initEncryptionKey(userDataPath)

    // 2. Open SQLite Database
    const dbPath = join(userDataPath, 'pullman.db')
    this.db = new Database(dbPath)
    this.db.pragma('journal_mode = WAL')

    // 3. Create Schema
    this.createTables()
  }

  private initEncryptionKey(userDataPath: string): void {
    const keyPath = join(userDataPath, '.master.key')
    if (existsSync(keyPath)) {
      try {
        const rawKey = readFileSync(keyPath)
        if (rawKey.length === 32) {
          this.encryptionKey = rawKey
          return
        }
      } catch {
        // regenerate below
      }
    }

    // Generate new 256-bit key
    const newKey = randomBytes(32)
    writeFileSync(keyPath, newKey)
    this.encryptionKey = newKey
  }

  private encrypt(plainText: string): string {
    if (!plainText || !this.encryptionKey) return ''
    try {
      const iv = randomBytes(12) // 96-bit IV for AES-GCM
      const cipher = createCipheriv('aes-256-gcm', this.encryptionKey, iv)
      let encrypted = cipher.update(plainText, 'utf8', 'hex')
      encrypted += cipher.final('hex')
      const authTag = cipher.getAuthTag().toString('hex')
      return `${iv.toString('hex')}:${authTag}:${encrypted}`
    } catch {
      return ''
    }
  }

  private decrypt(cipherText: string): string {
    if (!cipherText || !this.encryptionKey) return ''
    try {
      const parts = cipherText.split(':')
      if (parts.length !== 3) return ''
      const [ivHex, authTagHex, encryptedHex] = parts
      const decipher = createDecipheriv(
        'aes-256-gcm',
        this.encryptionKey,
        Buffer.from(ivHex, 'hex')
      )
      decipher.setAuthTag(Buffer.from(authTagHex, 'hex'))
      let decrypted = decipher.update(encryptedHex, 'hex', 'utf8')
      decrypted += decipher.final('utf8')
      return decrypted
    } catch {
      return ''
    }
  }

  private createTables(): void {
    if (!this.db) return

    this.db.exec(`
      CREATE TABLE IF NOT EXISTS connection_groups (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
      );

      CREATE TABLE IF NOT EXISTS connections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        url TEXT,
        type TEXT DEFAULT 'MariaDB',
        color TEXT DEFAULT 'blue',
        group_name TEXT,
        host TEXT NOT NULL,
        port INTEGER NOT NULL DEFAULT 3306,
        user TEXT NOT NULL,
        password_encrypted TEXT,
        save_password INTEGER DEFAULT 1,
        database_name TEXT,
        notes TEXT,
        remote_path TEXT DEFAULT '/var/www/app-backend',
        branch TEXT DEFAULT 'main',
        last_status TEXT DEFAULT 'Ready',
        last_status_type TEXT DEFAULT 'idle',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
      );
    `)
  }

  public getAllGroups(): string[] {
    if (!this.db) return []
    try {
      const rows = this.db
        .prepare('SELECT name FROM connection_groups ORDER BY name ASC')
        .all() as { name: string }[]
      const groupNames = rows.map((r) => r.name)
      const connGroups = this.db
        .prepare(
          'SELECT DISTINCT group_name FROM connections WHERE group_name IS NOT NULL AND group_name != ""'
        )
        .all() as { group_name: string }[]
      for (const cg of connGroups) {
        if (cg.group_name && !groupNames.includes(cg.group_name)) {
          groupNames.push(cg.group_name)
        }
      }
      return groupNames
    } catch {
      return []
    }
  }

  public addGroup(name: string): string {
    if (!this.db) throw new Error('Database not initialized')
    const trimmed = name.trim()
    if (!trimmed) throw new Error('Group name cannot be empty')
    this.db.prepare('INSERT OR IGNORE INTO connection_groups (name) VALUES (?)').run(trimmed)
    return trimmed
  }

  public renameGroup(oldName: string, newName: string): boolean {
    if (!this.db) return false
    const trimmed = newName.trim()
    const trimmedOld = oldName.trim()
    if (!trimmed || !trimmedOld) return false

    try {
      this.db.transaction(() => {
        // 1. Insert new group if not exists
        this.db!.prepare('INSERT OR IGNORE INTO connection_groups (name) VALUES (?)').run(trimmed)
        // 2. Update connections table
        this.db!.prepare(
          'UPDATE connections SET group_name = ? WHERE group_name = ? COLLATE NOCASE'
        ).run(trimmed, trimmedOld)
        // 3. Delete old group record
        this.db!.prepare('DELETE FROM connection_groups WHERE name = ? COLLATE NOCASE').run(
          trimmedOld
        )
      })()
      return true
    } catch (err) {
      console.error('Failed to rename group in SQLite:', err)
      return false
    }
  }

  public deleteGroup(name: string): boolean {
    if (!this.db) return false
    this.db.prepare('DELETE FROM connection_groups WHERE name = ?').run(name)
    this.db.prepare('UPDATE connections SET group_name = "" WHERE group_name = ?').run(name)
    return true
  }

  public getAllConnections(): ConnectionRecord[] {
    if (!this.db) return []

    const rows = this.db
      .prepare('SELECT * FROM connections ORDER BY group_name ASC, name ASC')
      .all() as Record<string, unknown>[]

    return rows.map((r) => this.mapRowToRecord(r))
  }

  public getConnectionById(id: number): ConnectionRecord | null {
    if (!this.db) return null
    const row = this.db.prepare('SELECT * FROM connections WHERE id = ?').get(id) as Record<
      string,
      unknown
    >
    return row ? this.mapRowToRecord(row) : null
  }

  public addConnection(input: ConnectionInput): ConnectionRecord {
    if (!this.db) throw new Error('Database not initialized')

    const encryptedPass = input.savePassword && input.password ? this.encrypt(input.password) : ''

    const stmt = this.db.prepare(`
      INSERT INTO connections (
        name, url, type, color, group_name, host, port, user, password_encrypted,
        save_password, database_name, notes, remote_path, branch, last_status, last_status_type
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `)

    const result = stmt.run(
      input.name,
      input.url || '',
      input.type || 'MariaDB',
      input.color || 'blue',
      input.group || '',
      input.host,
      input.port || 3306,
      input.user || 'root',
      encryptedPass,
      input.savePassword !== false ? 1 : 0,
      input.database || '',
      input.notes || '',
      input.remotePath || '/var/www/app-backend',
      input.branch || 'main',
      'Connected',
      'success'
    )

    const newId = Number(result.lastInsertRowid)
    return this.getConnectionById(newId)!
  }

  public deleteConnection(id: number): boolean {
    if (!this.db) return false
    const stmt = this.db.prepare('DELETE FROM connections WHERE id = ?')
    const result = stmt.run(id)
    return result.changes > 0
  }

  private mapRowToRecord(row: Record<string, unknown>): ConnectionRecord {
    const encryptedPass = String(row.password_encrypted || '')
    const pass = encryptedPass ? this.decrypt(encryptedPass) : ''

    return {
      id: Number(row.id),
      name: String(row.name),
      url: String(row.url || ''),
      type: String(row.type || 'MariaDB'),
      color: String(row.color || 'blue'),
      group: String(row.group_name || ''),
      host: String(row.host),
      port: Number(row.port),
      user: String(row.user),
      password: pass,
      savePassword: Boolean(row.save_password),
      database: String(row.database_name || ''),
      notes: String(row.notes || ''),
      remotePath: String(row.remote_path || ''),
      branch: String(row.branch || 'main'),
      status: String(row.last_status || 'Ready'),
      statusType: (row.last_status_type as 'success' | 'warning' | 'error' | 'idle') || 'idle',
      createdAt: String(row.created_at || ''),
      updatedAt: String(row.updated_at || '')
    }
  }
}

export const dbService = new DatabaseService()
