import { ref, computed } from 'vue'
import type { HostItem } from '../../../types/connection'
import type {
  DbTargetConfig,
  DatabaseSchema,
  TableSchema,
  TableColumnSchema,
  TableDiff,
  ColumnDiff,
  DiffStatus,
  TableFilterType,
  SchemaCompareSummary
} from '../types'

export function useSchemaCompare(hostsRef: { value: HostItem[] }) {
  const sourceConfig = ref<DbTargetConfig>({
    hostId: null,
    hostName: '',
    dbHost: '127.0.0.1',
    dbPort: 3306,
    dbUser: 'root',
    dbPassword: '',
    database: '',
    availableDatabases: [],
    isLoadingDbs: false,
    fetchError: null,
    showDbSettings: false
  })

  const targetConfig = ref<DbTargetConfig>({
    hostId: null,
    hostName: '',
    dbHost: '127.0.0.1',
    dbPort: 3306,
    dbUser: 'root',
    dbPassword: '',
    database: '',
    availableDatabases: [],
    isLoadingDbs: false,
    fetchError: null,
    showDbSettings: false
  })

  const isComparing = ref(false)
  const compareError = ref<string | null>(null)
  const sourceSchema = ref<DatabaseSchema | null>(null)
  const targetSchema = ref<DatabaseSchema | null>(null)
  const tableDiffs = ref<TableDiff[]>([])
  const selectedTableName = ref<string | null>(null)
  const filterType = ref<TableFilterType>('diff_only')
  const searchQuery = ref('')
  const showSqlModal = ref(false)

  function applyHostToConfig(config: DbTargetConfig, host: HostItem): void {
    config.hostId = host.id
    config.hostName = host.name
    config.dbHost = host.dbHost || '127.0.0.1'
    config.dbPort = host.dbPort || 3306
    config.dbUser = host.dbUser || host.user || 'root'
    config.dbPassword = host.dbPassword || host.password || ''
    config.database = host.database || ''
    config.sshHost = host.ip
    config.sshPort = host.port || 22
    config.sshUser = host.user || 'root'
    config.sshPassword = host.password || ''
    config.fetchError = null

    // If host already has a default database configured, prefill availableDatabases
    if (host.database && !config.availableDatabases.includes(host.database)) {
      config.availableDatabases = [host.database]
    }
  }

  function handleSelectSourceHost(hostId: number | null): void {
    if (hostId === null) {
      sourceConfig.value.hostId = null
      sourceConfig.value.hostName = ''
      sourceConfig.value.availableDatabases = []
      return
    }
    const host = hostsRef.value.find((h) => h.id === hostId)
    if (host) {
      applyHostToConfig(sourceConfig.value, host)
      fetchDatabases(sourceConfig.value)
    }
  }

  function handleSelectTargetHost(hostId: number | null): void {
    if (hostId === null) {
      targetConfig.value.hostId = null
      targetConfig.value.hostName = ''
      targetConfig.value.availableDatabases = []
      return
    }
    const host = hostsRef.value.find((h) => h.id === hostId)
    if (host) {
      applyHostToConfig(targetConfig.value, host)
      fetchDatabases(targetConfig.value)
    }
  }

  function buildTargetPayload(config: DbTargetConfig) {
    const hasSsh =
      config.sshHost &&
      config.sshHost.trim() !== '' &&
      config.sshHost !== '127.0.0.1' &&
      config.sshHost !== 'localhost'

    return {
      host: config.dbHost || '127.0.0.1',
      port: config.dbPort || 3306,
      user: config.dbUser || 'root',
      password: config.dbPassword || undefined,
      database: config.database || undefined,
      timeoutMs: 12000,
      ssh: hasSsh
        ? {
            host: config.sshHost!,
            port: config.sshPort || 22,
            user: config.sshUser || 'root',
            password: config.sshPassword || undefined
          }
        : undefined
    }
  }

  async function fetchDatabases(config: DbTargetConfig): Promise<void> {
    if (!window.api?.getDatabases) return
    config.isLoadingDbs = true
    config.fetchError = null
    try {
      const payload = buildTargetPayload(config)
      const res = await window.api.getDatabases(payload)
      if (res.success && res.databases && res.databases.length > 0) {
        config.availableDatabases = res.databases
        if (!config.database) {
          config.database = res.databases[0]
        }
      } else if (!res.success) {
        config.fetchError = res.error || 'Failed to connect to database'
        console.warn('fetchDatabases error:', res.error)
      }
    } catch (err: any) {
      config.fetchError = err?.message || String(err)
      console.warn('Failed to fetch databases:', err)
    } finally {
      config.isLoadingDbs = false
    }
  }

  function swapConfigs(): void {
    const temp = JSON.parse(JSON.stringify(sourceConfig.value))
    sourceConfig.value = JSON.parse(JSON.stringify(targetConfig.value))
    targetConfig.value = temp
    if (tableDiffs.value.length > 0) {
      compareSchemas()
    }
  }

  function generateColumnDefinition(c: TableColumnSchema): string {
    let def = `\`${c.name}\` ${c.columnType.toUpperCase()}`
    if (!c.isNullable) {
      def += ' NOT NULL'
    } else {
      def += ' NULL'
    }
    if (c.defaultValue !== null && c.defaultValue !== undefined) {
      const isExpression =
        c.defaultValue.toUpperCase().includes('CURRENT_TIMESTAMP') ||
        c.defaultValue.toUpperCase().includes('NULL')
      if (isExpression) {
        def += ` DEFAULT ${c.defaultValue}`
      } else {
        def += ` DEFAULT '${c.defaultValue}'`
      }
    }
    if (c.extra) {
      def += ` ${c.extra.toUpperCase()}`
    }
    if (c.comment) {
      def += ` COMMENT '${c.comment.replace(/'/g, "\\'")}'`
    }
    return def
  }

  function generateCreateTableSql(table: TableSchema): string {
    const lines: string[] = []
    const pkCols: string[] = []

    for (const c of table.columns) {
      lines.push('  ' + generateColumnDefinition(c))
      if (c.columnKey === 'PRI') {
        pkCols.push(`\`${c.name}\``)
      }
    }

    if (pkCols.length > 0) {
      lines.push(`  PRIMARY KEY (${pkCols.join(', ')})`)
    }

    let sql = `CREATE TABLE IF NOT EXISTS \`${table.name}\` (\n`
    sql += lines.join(',\n')
    sql += `\n) ENGINE=${table.engine || 'InnoDB'} DEFAULT CHARSET=utf8mb4;`
    return sql
  }

  function compareTableColumns(
    tableName: string,
    srcTable?: TableSchema,
    tgtTable?: TableSchema
  ): { diffs: ColumnDiff[]; sql: string[]; status: DiffStatus } {
    const diffs: ColumnDiff[] = []
    const sql: string[] = []

    if (srcTable && !tgtTable) {
      for (const col of srcTable.columns) {
        diffs.push({
          name: col.name,
          status: 'source_only',
          sourceCol: col,
          diffFields: ['missing_in_target']
        })
      }
      sql.push(generateCreateTableSql(srcTable))
      return { diffs, sql, status: 'source_only' }
    }

    if (!srcTable && tgtTable) {
      for (const col of tgtTable.columns) {
        diffs.push({
          name: col.name,
          status: 'target_only',
          targetCol: col,
          diffFields: ['missing_in_source']
        })
      }
      sql.push(`-- Table exists in target but missing in source:\n-- DROP TABLE \`${tableName}\`;`)
      return { diffs, sql, status: 'target_only' }
    }

    if (!srcTable || !tgtTable) {
      return { diffs: [], sql: [], status: 'identical' }
    }

    const srcColMap = new Map(srcTable.columns.map((c) => [c.name.toLowerCase(), c]))
    const tgtColMap = new Map(tgtTable.columns.map((c) => [c.name.toLowerCase(), c]))

    // Columns in source
    for (const sCol of srcTable.columns) {
      const key = sCol.name.toLowerCase()
      const tCol = tgtColMap.get(key)

      if (!tCol) {
        diffs.push({
          name: sCol.name,
          status: 'source_only',
          sourceCol: sCol,
          diffFields: ['missing_in_target']
        })
        sql.push(
          `ALTER TABLE \`${tableName}\` ADD COLUMN ${generateColumnDefinition(sCol)};`
        )
      } else {
        const diffFields: string[] = []

        const sType = sCol.columnType.toLowerCase().replace(/\s+/g, '')
        const tType = tCol.columnType.toLowerCase().replace(/\s+/g, '')
        if (sType !== tType) diffFields.push('type')

        if (sCol.isNullable !== tCol.isNullable) diffFields.push('nullable')

        const sDef = sCol.defaultValue !== null ? String(sCol.defaultValue).trim() : null
        const tDef = tCol.defaultValue !== null ? String(tCol.defaultValue).trim() : null
        if (sDef !== tDef) diffFields.push('default')

        const sExtra = sCol.extra.toLowerCase().trim()
        const tExtra = tCol.extra.toLowerCase().trim()
        if (sExtra !== tExtra) diffFields.push('extra')

        if (diffFields.length > 0) {
          diffs.push({
            name: sCol.name,
            status: 'modified',
            sourceCol: sCol,
            targetCol: tCol,
            diffFields
          })
          sql.push(
            `ALTER TABLE \`${tableName}\` MODIFY COLUMN ${generateColumnDefinition(sCol)};`
          )
        } else {
          diffs.push({
            name: sCol.name,
            status: 'identical',
            sourceCol: sCol,
            targetCol: tCol,
            diffFields: []
          })
        }
      }
    }

    // Columns in target but not in source
    for (const tCol of tgtTable.columns) {
      const key = tCol.name.toLowerCase()
      if (!srcColMap.has(key)) {
        diffs.push({
          name: tCol.name,
          status: 'target_only',
          targetCol: tCol,
          diffFields: ['missing_in_source']
        })
        sql.push(`-- Column exists in target only:\n-- ALTER TABLE \`${tableName}\` DROP COLUMN \`${tCol.name}\`;`)
      }
    }

    const hasDifferences = diffs.some((d) => d.status !== 'identical')
    return {
      diffs,
      sql,
      status: hasDifferences ? 'modified' : 'identical'
    }
  }

  async function compareSchemas(): Promise<void> {
    if (!sourceConfig.value.database || !targetConfig.value.database) {
      compareError.value = 'Please select both Source Database and Target Database.'
      return
    }

    isComparing.value = true
    compareError.value = null
    tableDiffs.value = []

    try {
      const srcPayload = buildTargetPayload(sourceConfig.value)
      const tgtPayload = buildTargetPayload(targetConfig.value)

      const [srcRes, tgtRes] = await Promise.all([
        window.api.getDatabaseSchema({ ...srcPayload, database: sourceConfig.value.database }),
        window.api.getDatabaseSchema({ ...tgtPayload, database: targetConfig.value.database })
      ])

      if (!srcRes.success || !srcRes.schema) {
        throw new Error(
          `Source Error (${sourceConfig.value.hostName || sourceConfig.value.dbHost}): ${srcRes.error || 'Failed to fetch source schema'}`
        )
      }
      if (!tgtRes.success || !tgtRes.schema) {
        throw new Error(
          `Target Error (${targetConfig.value.hostName || targetConfig.value.dbHost}): ${tgtRes.error || 'Failed to fetch target schema'}`
        )
      }

      sourceSchema.value = srcRes.schema
      targetSchema.value = tgtRes.schema

      const srcTables = srcRes.schema.tables || {}
      const tgtTables = tgtRes.schema.tables || {}

      const allTableNames = Array.from(
        new Set([...Object.keys(srcTables), ...Object.keys(tgtTables)])
      ).sort()

      const computedDiffs: TableDiff[] = []
      for (const name of allTableNames) {
        const srcT = srcTables[name]
        const tgtT = tgtTables[name]
        const { diffs, sql, status } = compareTableColumns(name, srcT, tgtT)

        computedDiffs.push({
          name,
          status,
          sourceTable: srcT,
          targetTable: tgtT,
          columnDiffs: diffs,
          syncSql: sql
        })
      }

      tableDiffs.value = computedDiffs

      // Select first modified table, or first table
      const firstDiff = computedDiffs.find((t) => t.status !== 'identical')
      if (firstDiff) {
        selectedTableName.value = firstDiff.name
      } else if (computedDiffs.length > 0) {
        selectedTableName.value = computedDiffs[0].name
      } else {
        selectedTableName.value = null
      }
    } catch (err: any) {
      compareError.value = err?.message || String(err)
    } finally {
      isComparing.value = false
    }
  }

  const summary = computed<SchemaCompareSummary>(() => {
    let identical = 0
    let modified = 0
    let sourceOnly = 0
    let targetOnly = 0
    let colDiffs = 0

    for (const t of tableDiffs.value) {
      if (t.status === 'identical') identical++
      else if (t.status === 'modified') modified++
      else if (t.status === 'source_only') sourceOnly++
      else if (t.status === 'target_only') targetOnly++

      colDiffs += t.columnDiffs.filter((c) => c.status !== 'identical').length
    }

    return {
      totalTables: tableDiffs.value.length,
      identicalTables: identical,
      modifiedTables: modified,
      sourceOnlyTables: sourceOnly,
      targetOnlyTables: targetOnly,
      totalColumnDiffs: colDiffs
    }
  })

  const filteredTableDiffs = computed(() => {
    return tableDiffs.value.filter((t) => {
      // Filter by status tab
      if (filterType.value === 'diff_only' && t.status === 'identical') return false
      if (filterType.value === 'modified' && t.status !== 'modified') return false
      if (filterType.value === 'source_only' && t.status !== 'source_only') return false
      if (filterType.value === 'target_only' && t.status !== 'target_only') return false
      if (filterType.value === 'identical' && t.status !== 'identical') return false

      // Filter by search query
      if (searchQuery.value.trim()) {
        const q = searchQuery.value.toLowerCase().trim()
        const matchName = t.name.toLowerCase().includes(q)
        const matchCol = t.columnDiffs.some((c) => c.name.toLowerCase().includes(q))
        if (!matchName && !matchCol) return false
      }

      return true
    })
  })

  const selectedTableDiff = computed<TableDiff | null>(() => {
    if (!selectedTableName.value) return null
    return tableDiffs.value.find((t) => t.name === selectedTableName.value) || null
  })

  const allSyncSql = computed<string>(() => {
    const chunks: string[] = []
    chunks.push(`-- ========================================================`)
    chunks.push(`-- SCHEMA MIGRATION / SYNC SCRIPT`)
    chunks.push(`-- Source: ${sourceConfig.value.hostName || sourceConfig.value.dbHost} (${sourceConfig.value.database})`)
    chunks.push(`-- Target: ${targetConfig.value.hostName || targetConfig.value.dbHost} (${targetConfig.value.database})`)
    chunks.push(`-- Generated: ${new Date().toISOString()}`)
    chunks.push(`-- Total Table Differences: ${summary.value.modifiedTables + summary.value.sourceOnlyTables + summary.value.targetOnlyTables}`)
    chunks.push(`-- Total Column Differences: ${summary.value.totalColumnDiffs}`)
    chunks.push(`-- ========================================================\n`)

    for (const t of tableDiffs.value) {
      if (t.syncSql.length > 0 && t.status !== 'identical') {
        chunks.push(`-- Table: \`${t.name}\` (${t.status})`)
        chunks.push(t.syncSql.join('\n\n'))
        chunks.push('')
      }
    }

    return chunks.join('\n')
  })

  const isSyncing = ref(false)
  const syncModalState = ref<{
    show: boolean
    title: string
    statements: string[]
    targetDatabase: string
    targetHost: string
    error: string | null
    success: boolean
  }>({
    show: false,
    title: '',
    statements: [],
    targetDatabase: '',
    targetHost: '',
    error: null,
    success: false
  })

  function openTableSync(table: TableDiff): void {
    const runnable = table.syncSql
      .map((s) => s.trim())
      .filter((s) => s.length > 0 && !s.startsWith('--'))
    if (runnable.length === 0) return

    syncModalState.value = {
      show: true,
      title: `Sync Table: \`${table.name}\``,
      statements: runnable,
      targetDatabase: targetConfig.value.database,
      targetHost: targetConfig.value.hostName || targetConfig.value.dbHost,
      error: null,
      success: false
    }
  }

  function openAllSync(): void {
    const runnable: string[] = []
    for (const t of tableDiffs.value) {
      if (t.status !== 'identical') {
        for (const s of t.syncSql) {
          const trimmed = s.trim()
          if (trimmed.length > 0 && !trimmed.startsWith('--')) {
            runnable.push(trimmed)
          }
        }
      }
    }
    if (runnable.length === 0) return

    syncModalState.value = {
      show: true,
      title: `Sync All Tables (${runnable.length} queries)`,
      statements: runnable,
      targetDatabase: targetConfig.value.database,
      targetHost: targetConfig.value.hostName || targetConfig.value.dbHost,
      error: null,
      success: false
    }
  }

  async function executePendingSync(): Promise<void> {
    if (syncModalState.value.statements.length === 0 || !window.api?.executeSyncSql) return
    isSyncing.value = true
    syncModalState.value.error = null

    try {
      if (!targetConfig.value.database) {
        throw new Error('Target database name is missing')
      }
      const payload = JSON.parse(JSON.stringify(buildTargetPayload(targetConfig.value)))
      const stmts = Array.from(syncModalState.value.statements || []).map((s) => String(s))
      const res = await window.api.executeSyncSql(
        { ...payload, database: targetConfig.value.database },
        stmts
      )
      if (!res.success) {
        const failedItem = res.results.find((r) => !r.success)
        throw new Error(failedItem?.error || res.error || 'Sync execution failed')
      }
      syncModalState.value.success = true
      setTimeout(() => {
        syncModalState.value.show = false
        compareSchemas()
      }, 1200)
    } catch (err: any) {
      syncModalState.value.error = err?.message || String(err)
    } finally {
      isSyncing.value = false
    }
  }

  return {
    sourceConfig,
    targetConfig,
    isComparing,
    compareError,
    sourceSchema,
    targetSchema,
    tableDiffs,
    selectedTableName,
    filterType,
    searchQuery,
    showSqlModal,
    summary,
    filteredTableDiffs,
    selectedTableDiff,
    allSyncSql,
    isSyncing,
    syncModalState,
    handleSelectSourceHost,
    handleSelectTargetHost,
    fetchDatabases,
    swapConfigs,
    compareSchemas,
    openTableSync,
    openAllSync,
    executePendingSync
  }
}
