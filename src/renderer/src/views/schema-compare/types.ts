export interface DbTargetConfig {
  hostId: number | null
  hostName: string
  dbHost: string
  dbPort: number
  dbUser: string
  dbPassword?: string
  database: string
  sshHost?: string
  sshPort?: number
  sshUser?: string
  sshPassword?: string
  availableDatabases: string[]
  isLoadingDbs: boolean
  fetchError?: string | null
  showDbSettings?: boolean
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

export type DiffStatus = 'identical' | 'modified' | 'source_only' | 'target_only'

export interface ColumnDiff {
  name: string
  status: DiffStatus
  sourceCol?: TableColumnSchema
  targetCol?: TableColumnSchema
  diffFields: string[] // 'type' | 'nullable' | 'default' | 'key' | 'extra'
}

export interface TableDiff {
  name: string
  status: DiffStatus
  sourceTable?: TableSchema
  targetTable?: TableSchema
  columnDiffs: ColumnDiff[]
  syncSql: string[]
}

export type TableFilterType =
  | 'all'
  | 'diff_only'
  | 'modified'
  | 'source_only'
  | 'target_only'
  | 'identical'

export interface SchemaCompareSummary {
  totalTables: number
  identicalTables: number
  modifiedTables: number
  sourceOnlyTables: number
  targetOnlyTables: number
  totalColumnDiffs: number
}
