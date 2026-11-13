import Database from 'better-sqlite3'
import { app } from 'electron'
import { join, dirname } from 'path'
import { existsSync, mkdirSync, readFileSync, writeFileSync, copyFileSync } from 'fs'
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
  dbHost?: string
  dbPort?: number
  dbUser?: string
  dbPassword?: string
  dbSavePassword?: boolean
  isProduction?: boolean
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
  dbHost?: string
  dbPort?: number
  dbUser?: string
  dbPassword?: string
  dbSavePassword?: boolean
  isProduction?: boolean
}

class DatabaseService {
  private db: Database.Database | null = null
  private encryptionKey: Buffer | null = null

  public init(): void {
    const userDataPath = app?.getPath ? app.getPath('userData') : process.cwd()
    if (!existsSync(userDataPath)) {
      mkdirSync(userDataPath, { recursive: true })
    }

    // Auto-migrate database & key from previous app paths if current path is empty
    this.migrateFromLegacyIfEmpty(userDataPath)

    // 1. Initialize Encryption Key (.master.key)
    this.initEncryptionKey(userDataPath)

    // 2. Open SQLite Database
    const dbPath = join(userDataPath, 'pullman.db')
    this.db = new Database(dbPath)
    this.db.pragma('journal_mode = WAL')

    // 3. Create Schema
    this.createTables()
  }

  private migrateFromLegacyIfEmpty(userDataPath: string): void {
    const dbPath = join(userDataPath, 'pullman.db')
    const keyPath = join(userDataPath, '.master.key')

    if (existsSync(dbPath)) {
      try {
        const currentDb = new Database(dbPath, { readonly: true })
        const hasTable = currentDb
          .prepare("SELECT count(*) as count FROM sqlite_master WHERE type='table' AND name='connections'")
          .get() as { count: number } | undefined
        if (hasTable && hasTable.count > 0) {
          const connCount = currentDb.prepare('SELECT count(*) as count FROM connections').get() as
            | { count: number }
            | undefined
          currentDb.close()
          if (connCount && connCount.count > 0) {
            return
          }
        } else {
          currentDb.close()
        }
      } catch {
        // Continue to check legacy candidates
      }
    }

    const parentDir = dirname(userDataPath)
    const candidates = ['pullman-app', 'Pullman', 'DO.MBA Pull Manager', 'domba-pull-manager']

    for (const name of candidates) {
      const candidateDir = join(parentDir, name)
      if (candidateDir === userDataPath || !existsSync(candidateDir)) continue

      const candidateDbPath = join(candidateDir, 'pullman.db')
      const candidateKeyPath = join(candidateDir, '.master.key')

      if (existsSync(candidateDbPath) && existsSync(candidateKeyPath)) {
        try {
          const testDb = new Database(candidateDbPath, { readonly: true })
          const hasTable = testDb
            .prepare("SELECT count(*) as count FROM sqlite_master WHERE type='table' AND name='connections'")
            .get() as { count: number } | undefined
          if (hasTable && hasTable.count > 0) {
            const count = testDb.prepare('SELECT count(*) as count FROM connections').get() as
              | { count: number }
              | undefined
            testDb.close()
            if (count && count.count > 0) {
              console.log(`[DatabaseService] Migrating ${count.count} connections from ${candidateDir}`)
              copyFileSync(candidateKeyPath, keyPath)
              copyFileSync(candidateDbPath, dbPath)
              return
            }
          } else {
            testDb.close()
          }
        } catch (e) {
          console.warn('[DatabaseService] Failed to check candidate legacy db:', e)
        }
      }
    }
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
        db_host TEXT DEFAULT '127.0.0.1',
        db_port INTEGER DEFAULT 3306,
        db_user TEXT DEFAULT 'root',
        db_password_encrypted TEXT,
        db_save_password INTEGER DEFAULT 1,
        is_production INTEGER DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
      );

      CREATE TABLE IF NOT EXISTS database_connections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        connection_id INTEGER NOT NULL UNIQUE,
        host TEXT DEFAULT '127.0.0.1',
        port INTEGER DEFAULT 3306,
        user TEXT DEFAULT 'root',
        password_encrypted TEXT,
        save_password INTEGER DEFAULT 1,
        database_name TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (connection_id) REFERENCES connections(id) ON DELETE CASCADE
      );
    `)

    // Safe migration if table already exists
    const columnsToAdd = [
      { name: 'db_host', type: "TEXT DEFAULT '127.0.0.1'" },
      { name: 'db_port', type: 'INTEGER DEFAULT 3306' },
      { name: 'db_user', type: "TEXT DEFAULT 'root'" },
      { name: 'db_password_encrypted', type: 'TEXT' },
      { name: 'db_save_password', type: 'INTEGER DEFAULT 1' },
      { name: 'is_production', type: 'INTEGER DEFAULT 0' }
    ]
    for (const col of columnsToAdd) {
      try {
        this.db.exec(`ALTER TABLE connections ADD COLUMN ${col.name} ${col.type}`)
      } catch {
        // column already exists
      }
    }
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
    try {
      this.db.transaction(() => {
        this.db!
          .prepare(
            `DELETE FROM database_connections WHERE connection_id IN (
              SELECT id FROM connections WHERE group_name = ? COLLATE NOCASE
            )`
          )
          .run(name)
        this.db!.prepare('DELETE FROM connections WHERE group_name = ? COLLATE NOCASE').run(name)
        this.db!.prepare('DELETE FROM connection_groups WHERE name = ? COLLATE NOCASE').run(name)
      })()
      return true
    } catch (err) {
      console.error('Failed to delete group and its connections:', err)
      return false
    }
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

    const groupToInsert = (input.group || '').trim()
    if (groupToInsert) {
      this.db
        .prepare('INSERT OR IGNORE INTO connection_groups (name) VALUES (?)')
        .run(groupToInsert)
    }

    const encryptedPass =
      input.savePassword !== false && input.password ? this.encrypt(input.password) : ''
    const encryptedDbPass =
      input.dbSavePassword !== false && input.dbPassword ? this.encrypt(input.dbPassword) : ''

    const stmt = this.db.prepare(`
      INSERT INTO connections (
        name, url, type, color, group_name, host, port, user, password_encrypted,
        save_password, database_name, notes, remote_path, branch, last_status, last_status_type,
        db_host, db_port, db_user, db_password_encrypted, db_save_password, is_production
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `)

    const result = stmt.run(
      input.name,
      input.url || '',
      input.type || 'MariaDB',
      input.color || 'blue',
      input.group || '',
      input.host,
      input.port || 22,
      input.user || 'root',
      encryptedPass,
      input.savePassword !== false ? 1 : 0,
      input.database || '',
      input.notes || '',
      input.remotePath !== undefined ? input.remotePath : '',
      input.branch || 'main',
      'Connected',
      'success',
      input.dbHost || '127.0.0.1',
      input.dbPort || 3306,
      input.dbUser || 'root',
      encryptedDbPass,
      input.dbSavePassword !== false ? 1 : 0,
      input.isProduction ? 1 : 0
    )

    const newId = Number(result.lastInsertRowid)

    try {
      this.db
        .prepare(`
          INSERT INTO database_connections (
            connection_id, host, port, user, password_encrypted, save_password, database_name
          ) VALUES (?, ?, ?, ?, ?, ?, ?)
        `)
        .run(
          newId,
          input.dbHost || '127.0.0.1',
          input.dbPort || 3306,
          input.dbUser || 'root',
          encryptedDbPass,
          input.dbSavePassword !== false ? 1 : 0,
          input.database || ''
        )
    } catch (err) {
      console.error('Failed to insert into database_connections:', err)
    }

    return this.getConnectionById(newId)!
  }

  public updateConnection(id: number, input: ConnectionInput): ConnectionRecord {
    if (!this.db) throw new Error('Database not initialized')

    const existing = this.getConnectionById(id)
    if (!existing) {
      throw new Error(`Connection with id ${id} not found`)
    }

    const groupToInsert = (input.group || '').trim()
    if (groupToInsert) {
      this.db
        .prepare('INSERT OR IGNORE INTO connection_groups (name) VALUES (?)')
        .run(groupToInsert)
    }

    let encryptedPass: string | null = null
    if (input.savePassword === false) {
      encryptedPass = ''
    } else if (typeof input.password === 'string' && input.password.length > 0) {
      encryptedPass = this.encrypt(input.password)
    }

    let encryptedDbPass: string | null = null
    if (input.dbSavePassword === false) {
      encryptedDbPass = ''
    } else if (typeof input.dbPassword === 'string' && input.dbPassword.length > 0) {
      encryptedDbPass = this.encrypt(input.dbPassword)
    }

    const remotePath = input.remotePath !== undefined ? input.remotePath : existing.remotePath
    const branch = input.branch !== undefined ? input.branch : existing.branch
    const dbHost = input.dbHost !== undefined ? input.dbHost : (existing.dbHost || '127.0.0.1')
    const dbPort = input.dbPort !== undefined ? input.dbPort : (existing.dbPort || 3306)
    const dbUser = input.dbUser !== undefined ? input.dbUser : (existing.dbUser || 'root')
    const dbSavePassword =
      input.dbSavePassword !== undefined
        ? input.dbSavePassword
        : existing.dbSavePassword !== false

    const finalPass = encryptedPass !== null ? encryptedPass : (existing.password ? this.encrypt(existing.password) : '')
    const finalDbPass = encryptedDbPass !== null ? encryptedDbPass : (existing.dbPassword ? this.encrypt(existing.dbPassword) : '')

    this.db
      .prepare(
        `
        UPDATE connections SET
          name = ?, url = ?, type = ?, color = ?, group_name = ?,
          host = ?, port = ?, user = ?, password_encrypted = ?,
          save_password = ?, database_name = ?, notes = ?, remote_path = ?, branch = ?,
          db_host = ?, db_port = ?, db_user = ?, db_password_encrypted = ?, db_save_password = ?,
          is_production = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
      `
      )
      .run(
        input.name,
        input.url || '',
        input.type || 'MariaDB',
        input.color || 'blue',
        input.group || '',
        input.host,
        input.port || 22,
        input.user || 'root',
        finalPass,
        input.savePassword !== false ? 1 : 0,
        input.database !== undefined ? input.database : (existing.database || ''),
        input.notes !== undefined ? input.notes : (existing.notes || ''),
        remotePath !== undefined ? remotePath : '',
        branch || 'main',
        dbHost,
        dbPort,
        dbUser,
        finalDbPass,
        dbSavePassword ? 1 : 0,
        input.isProduction !== undefined ? (input.isProduction ? 1 : 0) : (existing.isProduction ? 1 : 0),
        id
      )

    try {
      this.db
        .prepare(`
          INSERT INTO database_connections (
            connection_id, host, port, user, password_encrypted, save_password, database_name, updated_at
          ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
          ON CONFLICT(connection_id) DO UPDATE SET
            host = excluded.host,
            port = excluded.port,
            user = excluded.user,
            password_encrypted = excluded.password_encrypted,
            save_password = excluded.save_password,
            database_name = excluded.database_name,
            updated_at = CURRENT_TIMESTAMP
        `)
        .run(
          id,
          dbHost,
          dbPort,
          dbUser,
          finalDbPass,
          dbSavePassword ? 1 : 0,
          input.database !== undefined ? input.database : (existing.database || '')
        )
    } catch (err) {
      console.error('Failed to upsert database_connections:', err)
    }

    return this.getConnectionById(id)!
  }

  public deleteConnection(id: number): boolean {
    if (!this.db) return false
    try {
      this.db.prepare('DELETE FROM database_connections WHERE connection_id = ?').run(id)
    } catch {
      // ignore
    }
    const stmt = this.db.prepare('DELETE FROM connections WHERE id = ?')
    const result = stmt.run(id)
    return result.changes > 0
  }

  public importMultipleConnections(
    inputs: ConnectionInput[],
    extraGroups?: string[]
  ): { imported: number; failed: number } {
    if (!this.db) throw new Error('Database not initialized')
    let imported = 0
    let failed = 0
    const insertTx = this.db.transaction((items: ConnectionInput[]) => {
      if (Array.isArray(extraGroups)) {
        for (const g of extraGroups) {
          if (g && g.trim()) {
            try {
              this.addGroup(g.trim())
            } catch {
              // ignore
            }
          }
        }
      }
      for (const item of items) {
        try {
          if (item.group && item.group.trim()) {
            try {
              this.addGroup(item.group.trim())
            } catch {
              // ignore
            }
          }
          this.addConnection(item)
          imported++
        } catch (err) {
          console.error('Failed to import connection:', item.name, err)
          failed++
        }
      }
    })
    insertTx(inputs)
    return { imported, failed }
  }

  private mapRowToRecord(row: Record<string, unknown>): ConnectionRecord {
    const encryptedPass = String(row.password_encrypted || '')
    const pass = encryptedPass ? this.decrypt(encryptedPass) : ''

    const encryptedDbPass = String(row.db_password_encrypted || '')
    const dbPass = encryptedDbPass ? this.decrypt(encryptedDbPass) : ''

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
      dbHost: String(row.db_host || '127.0.0.1'),
      dbPort: Number(row.db_port || 3306),
      dbUser: String(row.db_user || 'root'),
      dbPassword: dbPass,
      dbSavePassword: row.db_save_password !== undefined && row.db_save_password !== null ? Boolean(row.db_save_password) : true,
      isProduction: Boolean(row.is_production),
      createdAt: String(row.created_at || ''),
      updatedAt: String(row.updated_at || '')
    }
  }
}

export const dbService = new DatabaseService()
