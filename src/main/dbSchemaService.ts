import { ipcMain } from 'electron'
import mysql from 'mysql2/promise'
import { Client as SshClient } from 'ssh2'

export interface DbTargetInput {
  host: string
  port: number
  user: string
  password?: string
  database?: string
  timeoutMs?: number
  ssh?: {
    host: string
    port: number
    user: string
    password?: string
  }
}

export interface TableColumnSchema {
  name: string
  ordinalPosition: number
  dataType: string
  columnType: string
  isNullable: boolean
  defaultValue: string | null
  columnKey: string
  extra: string
  comment?: string
}

export interface TableIndexSchema {
  name: string
  nonUnique: boolean
  columnName: string
  seqInIndex: number
  indexType: string
}

export interface TableSchema {
  name: string
  type: string
  engine?: string
  rows?: number
  collation?: string
  comment?: string
  columns: TableColumnSchema[]
  indexes: TableIndexSchema[]
}

export interface DatabaseSchema {
  database: string
  tables: Record<string, TableSchema>
}

export class DbSchemaService {
  private createSshTunnel(params: {
    sshHost: string
    sshPort: number
    sshUser: string
    sshPassword?: string
    targetHost: string
    targetPort: number
    timeoutMs: number
  }): Promise<{ stream: any; close: () => void }> {
    return new Promise((resolve, reject) => {
      const conn = new SshClient()
      let closed = false
      let timer: NodeJS.Timeout | null = null

      const cleanup = (): void => {
        if (!closed) {
          closed = true
          if (timer) clearTimeout(timer)
          try {
            conn.end()
          } catch {
            // ignore
          }
          try {
            conn.destroy()
          } catch {
            // ignore
          }
        }
      }

      timer = setTimeout(() => {
        cleanup()
        reject(new Error(`SSH tunnel timed out connecting to ${params.sshHost}:${params.sshPort}`))
      }, params.timeoutMs)

      conn.on('ready', () => {
        conn.forwardOut(
          '127.0.0.1',
          0,
          params.targetHost,
          params.targetPort,
          (err, stream) => {
            if (timer) clearTimeout(timer)
            if (err) {
              cleanup()
              reject(err)
              return
            }
            stream.on('close', cleanup)
            resolve({
              stream,
              close: cleanup
            })
          }
        )
      })

      conn.on('error', (err) => {
        cleanup()
        reject(err)
      })

      conn.on('keyboard-interactive', (_name, _instructions, _instructionsLang, prompts, finishInteractive) => {
        if (prompts.length > 0 && params.sshPassword) {
          finishInteractive([params.sshPassword])
        } else {
          finishInteractive([])
        }
      })

      try {
        conn.connect({
          host: params.sshHost,
          port: params.sshPort,
          username: params.sshUser,
          password: params.sshPassword || undefined,
          tryKeyboard: Boolean(params.sshPassword),
          readyTimeout: params.timeoutMs,
          hostVerifier: () => true
        })
      } catch (err) {
        cleanup()
        reject(err)
      }
    })
  }

  private async execRemoteSshCommand(
    sshConfig: { host: string; port: number; user: string; password?: string },
    command: string,
    timeoutMs: number = 10000
  ): Promise<{ stdout: string; stderr: string; code: number }> {
    return new Promise((resolve, reject) => {
      const conn = new SshClient()
      let timer: NodeJS.Timeout | null = null

      timer = setTimeout(() => {
        try {
          conn.destroy()
        } catch {
          // ignore
        }
        reject(new Error('SSH command timed out'))
      }, timeoutMs)

      conn.on('ready', () => {
        conn.exec(command, (err, stream) => {
          if (err) {
            if (timer) clearTimeout(timer)
            try {
              conn.end()
            } catch {
              // ignore
            }
            return reject(err)
          }

          let stdout = ''
          let stderr = ''
          stream.on('data', (data: Buffer) => {
            stdout += data.toString('utf8')
          })
          stream.stderr.on('data', (data: Buffer) => {
            stderr += data.toString('utf8')
          })
          stream.on('close', (code: number) => {
            if (timer) clearTimeout(timer)
            try {
              conn.end()
            } catch {
              // ignore
            }
            resolve({ stdout, stderr, code: code ?? 0 })
          })
        })
      })

      conn.on('error', (err) => {
        if (timer) clearTimeout(timer)
        reject(err)
      })

      conn.on('keyboard-interactive', (_name, _instructions, _instructionsLang, prompts, finishInteractive) => {
        if (prompts.length > 0 && sshConfig.password) {
          finishInteractive([sshConfig.password])
        } else {
          finishInteractive([])
        }
      })

      try {
        conn.connect({
          host: sshConfig.host,
          port: sshConfig.port,
          username: sshConfig.user,
          password: sshConfig.password || undefined,
          tryKeyboard: Boolean(sshConfig.password),
          readyTimeout: timeoutMs,
          hostVerifier: () => true
        })
      } catch (err) {
        if (timer) clearTimeout(timer)
        reject(err)
      }
    })
  }

  private async createConnection(
    target: DbTargetInput
  ): Promise<{ conn: mysql.Connection; close: () => void }> {
    const timeoutMs = target.timeoutMs || 10000
    let cleanupTunnel: (() => void) | null = null

    const connectionConfig: any = {
      user: target.user || 'root',
      password: target.password || undefined,
      database: target.database || undefined,
      connectTimeout: timeoutMs
    }

    const hasRemoteSsh =
      target.ssh?.host &&
      target.ssh.host.trim() !== '' &&
      target.ssh.host !== '127.0.0.1' &&
      target.ssh.host !== 'localhost'

    if (hasRemoteSsh && target.ssh) {
      const tunnel = await this.createSshTunnel({
        sshHost: target.ssh.host,
        sshPort: target.ssh.port,
        sshUser: target.ssh.user,
        sshPassword: target.ssh.password,
        targetHost: target.host || '127.0.0.1',
        targetPort: target.port || 3306,
        timeoutMs
      })
      connectionConfig.stream = tunnel.stream
      cleanupTunnel = tunnel.close
    } else {
      connectionConfig.host = target.host || '127.0.0.1'
      connectionConfig.port = target.port || 3306
    }

    const conn = await mysql.createConnection(connectionConfig)
    return {
      conn,
      close: () => {
        try {
          conn.end().catch(() => {})
        } catch {
          // ignore
        }
        if (cleanupTunnel) {
          cleanupTunnel()
        }
      }
    }
  }

  public async getDatabases(
    target: DbTargetInput
  ): Promise<{ success: boolean; databases?: string[]; error?: string }> {
    let connObj: { conn: mysql.Connection; close: () => void } | null = null
    const systemDbs = ['information_schema', 'performance_schema', 'mysql', 'sys']

    // Strategy 1: TCP connection (direct or via SSH tunnel)
    try {
      connObj = await this.createConnection({ ...target, database: undefined })
      const [rows] = await connObj.conn.query('SHOW DATABASES;')
      const dbs = (rows as any[])
        .map((r) => r.Database || Object.values(r)[0])
        .filter((name: string) => typeof name === 'string' && !systemDbs.includes(name.toLowerCase()))
        .sort()
      return { success: true, databases: dbs }
    } catch (primaryErr: any) {
      // If TCP fails and SSH is available, try Strategy 2: execute mysql CLI on remote host
      if (target.ssh?.host) {
        try {
          const cliCommands: string[] = []
          const u = target.user || 'root'
          const p = target.password ? `-p'${target.password.replace(/'/g, "'\\''")}'` : ''
          const h = target.host && target.host !== '127.0.0.1' ? `-h ${target.host}` : ''
          const P = target.port && target.port !== 3306 ? `-P ${target.port}` : ''

          // 1. With credentials
          cliCommands.push(`mysql ${h} ${P} -u ${u} ${p} -e "SHOW DATABASES;" 2>/dev/null`)
          // 2. Without password flag
          if (p) {
            cliCommands.push(`mysql ${h} ${P} -u ${u} -e "SHOW DATABASES;" 2>/dev/null`)
          }
          // 3. Sudo / local socket fallback
          cliCommands.push(`sudo mysql -e "SHOW DATABASES;" 2>/dev/null`)
          cliCommands.push(`mariadb -e "SHOW DATABASES;" 2>/dev/null`)

          for (const cmd of cliCommands) {
            try {
              const res = await this.execRemoteSshCommand(target.ssh, cmd, 8000)
              if (res.code === 0 && res.stdout.trim()) {
                const lines = res.stdout
                  .split('\n')
                  .map((l) => l.trim())
                  .filter(
                    (name) =>
                      name &&
                      name.toLowerCase() !== 'database' &&
                      !systemDbs.includes(name.toLowerCase())
                  )
                  .sort()
                if (lines.length > 0) {
                  return { success: true, databases: lines }
                }
              }
            } catch {
              // try next command
            }
          }
        } catch {
          // ignore CLI fallback error and return primaryErr
        }
      }

      return {
        success: false,
        error: primaryErr?.message || String(primaryErr)
      }
    } finally {
      if (connObj) {
        connObj.close()
      }
    }
  }

  public async getDatabaseSchema(
    target: DbTargetInput
  ): Promise<{ success: boolean; schema?: DatabaseSchema; error?: string }> {
    if (!target.database) {
      return { success: false, error: 'Database name is required' }
    }
    let connObj: { conn: mysql.Connection; close: () => void } | null = null
    try {
      connObj = await this.createConnection(target)

      // 1. Fetch tables
      const [tableRows] = await connObj.conn.query(
        `SELECT TABLE_NAME, TABLE_TYPE, ENGINE, TABLE_ROWS, TABLE_COLLATION, TABLE_COMMENT 
         FROM information_schema.TABLES 
         WHERE TABLE_SCHEMA = ? 
         ORDER BY TABLE_NAME`,
        [target.database]
      )

      // 2. Fetch columns
      const [columnRows] = await connObj.conn.query(
        `SELECT 
           TABLE_NAME, 
           COLUMN_NAME, 
           ORDINAL_POSITION, 
           COLUMN_DEFAULT, 
           IS_NULLABLE, 
           DATA_TYPE, 
           CHARACTER_MAXIMUM_LENGTH, 
           NUMERIC_PRECISION, 
           NUMERIC_SCALE, 
           COLUMN_TYPE, 
           COLUMN_KEY, 
           EXTRA, 
           COLUMN_COMMENT 
         FROM information_schema.COLUMNS 
         WHERE TABLE_SCHEMA = ? 
         ORDER BY TABLE_NAME, ORDINAL_POSITION`,
        [target.database]
      )

      // 3. Fetch indexes
      const [indexRows] = await connObj.conn.query(
        `SELECT 
           TABLE_NAME, 
           NON_UNIQUE, 
           INDEX_NAME, 
           SEQ_IN_INDEX, 
           COLUMN_NAME, 
           INDEX_TYPE 
         FROM information_schema.STATISTICS 
         WHERE TABLE_SCHEMA = ? 
         ORDER BY TABLE_NAME, INDEX_NAME, SEQ_IN_INDEX`,
        [target.database]
      )

      const tables: Record<string, TableSchema> = {}
      for (const t of tableRows as any[]) {
        tables[t.TABLE_NAME] = {
          name: t.TABLE_NAME,
          type: t.TABLE_TYPE || 'BASE TABLE',
          engine: t.ENGINE || 'InnoDB',
          rows: t.TABLE_ROWS || 0,
          collation: t.TABLE_COLLATION || '',
          comment: t.TABLE_COMMENT || '',
          columns: [],
          indexes: []
        }
      }

      for (const c of columnRows as any[]) {
        if (tables[c.TABLE_NAME]) {
          tables[c.TABLE_NAME].columns.push({
            name: c.COLUMN_NAME,
            ordinalPosition: c.ORDINAL_POSITION,
            dataType: c.DATA_TYPE,
            columnType: c.COLUMN_TYPE,
            isNullable: c.IS_NULLABLE === 'YES',
            defaultValue: c.COLUMN_DEFAULT !== null ? String(c.COLUMN_DEFAULT) : null,
            columnKey: c.COLUMN_KEY || '',
            extra: c.EXTRA || '',
            comment: c.COLUMN_COMMENT || ''
          })
        }
      }

      for (const idx of indexRows as any[]) {
        if (tables[idx.TABLE_NAME]) {
          tables[idx.TABLE_NAME].indexes.push({
            name: idx.INDEX_NAME,
            nonUnique: Boolean(idx.NON_UNIQUE),
            columnName: idx.COLUMN_NAME,
            seqInIndex: idx.SEQ_IN_INDEX,
            indexType: idx.INDEX_TYPE || 'BTREE'
          })
        }
      }

      return {
        success: true,
        schema: {
          database: target.database,
          tables
        }
      }
    } catch (err: any) {
      return { success: false, error: err?.message || String(err) }
    } finally {
      if (connObj) {
        connObj.close()
      }
    }
  }

  public async executeSyncSql(
    target: DbTargetInput,
    statements: string[]
  ): Promise<{
    success: boolean
    results: { statement: string; success: boolean; error?: string }[]
    error?: string
  }> {
    if (!target.database) {
      return { success: false, results: [], error: 'Target database is required' }
    }

    // Filter out comments and empty lines
    const runnableStatements = statements
      .map((s) => s.trim())
      .filter((s) => s.length > 0 && !s.startsWith('--'))

    if (runnableStatements.length === 0) {
      return { success: true, results: [] }
    }

    const results: { statement: string; success: boolean; error?: string }[] = []
    let connObj: { conn: mysql.Connection; close: () => void } | null = null

    try {
      connObj = await this.createConnection(target)
      for (const stmt of runnableStatements) {
        try {
          await connObj.conn.query(stmt)
          results.push({ statement: stmt, success: true })
        } catch (err: any) {
          results.push({ statement: stmt, success: false, error: err?.message || String(err) })
        }
      }
      const hasErrors = results.some((r) => !r.success)
      return {
        success: !hasErrors,
        results,
        error: hasErrors ? 'One or more SQL statements failed to execute' : undefined
      }
    } catch (primaryErr: any) {
      // If TCP fails and SSH is available, try remote SSH CLI execution
      if (target.ssh?.host) {
        try {
          const u = target.user || 'root'
          const p = target.password ? `-p'${target.password.replace(/'/g, "'\\''")}'` : ''
          const h = target.host && target.host !== '127.0.0.1' ? `-h ${target.host}` : ''
          const P = target.port && target.port !== 3306 ? `-P ${target.port}` : ''

          for (const stmt of runnableStatements) {
            const escStmt = stmt.replace(/'/g, "'\\''")
            let cmd = `mysql ${h} ${P} -u ${u} ${p} -D '${target.database}' -e '${escStmt}'`
            let res = await this.execRemoteSshCommand(target.ssh, cmd, 15000)
            if (res.code !== 0) {
              const sudoCmd = `sudo mysql -D '${target.database}' -e '${escStmt}'`
              res = await this.execRemoteSshCommand(target.ssh, sudoCmd, 15000)
            }
            if (res.code === 0) {
              results.push({ statement: stmt, success: true })
            } else {
              results.push({
                statement: stmt,
                success: false,
                error: res.stderr || 'Execution failed'
              })
            }
          }
          const hasErrors = results.some((r) => !r.success)
          return {
            success: !hasErrors,
            results,
            error: hasErrors ? 'One or more SQL statements failed to execute' : undefined
          }
        } catch (cliErr: any) {
          return { success: false, results, error: cliErr?.message || String(cliErr) }
        }
      }

      return {
        success: false,
        results,
        error: primaryErr?.message || String(primaryErr)
      }
    } finally {
      if (connObj) {
        connObj.close()
      }
    }
  }

  public registerIpcHandlers(): void {
    ipcMain.handle('database:get-databases', (_, target: DbTargetInput) => {
      return this.getDatabases(target)
    })

    ipcMain.handle('database:get-schema', (_, target: DbTargetInput) => {
      return this.getDatabaseSchema(target)
    })

    ipcMain.handle(
      'database:execute-sync-sql',
      (_, { target, statements }: { target: DbTargetInput; statements: string[] }) => {
        return this.executeSyncSql(target, statements)
      }
    )
  }
}

export const dbSchemaService = new DbSchemaService()
