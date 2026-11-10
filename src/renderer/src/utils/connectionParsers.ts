import { HostItem } from '../types/connection'

export interface ParsedConnectionItem {
  name: string
  host: string
  port: number
  user: string
  password?: string
  savePassword?: boolean
  group?: string
  type?: string
  color?: string
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
  selected?: boolean
}

/**
 * Parses JSON configurations into standardized connection items.
 * Supports Pullman's native export, array of configs, or nested object.
 */
export function parseJsonConnections(raw: string): ParsedConnectionItem[] {
  if (!raw || !raw.trim()) return []
  const parsed = JSON.parse(raw.trim())
  let items: any[] = []

  if (Array.isArray(parsed)) {
    items = parsed
  } else if (parsed && typeof parsed === 'object') {
    if (Array.isArray(parsed.connections)) {
      items = parsed.connections
    } else if (Array.isArray(parsed.hosts)) {
      items = parsed.hosts
    } else if (Array.isArray(parsed.items)) {
      items = parsed.items
    } else {
      // Maybe dictionary of connections
      items = Object.values(parsed)
    }
  }

  return items
    .filter((item) => item && typeof item === 'object')
    .map((item) => {
      const host = String(item.host || item.ip || item.hostname || item.server || '127.0.0.1').trim()
      const port = Number(item.port) || 22
      const user = String(item.user || item.username || 'root').trim()
      const name = String(item.name || item.title || `${user}@${host}`).trim()
      const group = String(item.group || item.folder || item.category || item.group_name || 'Imported').trim()
      const type = String(item.type || 'MariaDB')
      const color = String(item.color || 'blue')
      const password = item.password !== undefined ? String(item.password) : ''
      const database = String(item.database || item.db || item.database_name || '').trim()
      const remotePath = String(item.remotePath || item.remote_path || item.path || '').trim()
      const branch = String(item.branch || 'main').trim()
      const notes = String(item.notes || '')

      const dbHost = String(item.dbHost || item.db_host || host || '127.0.0.1').trim()
      const dbPort = Number(item.dbPort || item.db_port) || (database ? 3306 : port)
      const dbUser = String(item.dbUser || item.db_user || user || 'root').trim()
      const dbPassword = item.dbPassword !== undefined ? String(item.dbPassword) : password

      return {
        name,
        host,
        port,
        user,
        password,
        savePassword: item.savePassword !== false,
        group: group || 'Imported',
        type,
        color,
        database,
        notes,
        remotePath,
        branch,
        dbHost,
        dbPort,
        dbUser,
        dbPassword,
        dbSavePassword: item.dbSavePassword !== false,
        isProduction: Boolean(item.isProduction || item.is_production),
        selected: true
      }
    })
}

/**
 * Parses CSV lines handling quoted values, commas or semicolons.
 */
function parseCsvLine(line: string, delimiter: string): string[] {
  const result: string[] = []
  let cur = ''
  let inQuotes = false

  for (let i = 0; i < line.length; i++) {
    const char = line[i]
    if (char === '"') {
      if (inQuotes && line[i + 1] === '"') {
        cur += '"'
        i++
      } else {
        inQuotes = !inQuotes
      }
    } else if (char === delimiter && !inQuotes) {
      result.push(cur.trim())
      cur = ''
    } else {
      cur += char
    }
  }
  result.push(cur.trim())
  return result
}

/**
 * Parses CSV configurations into standardized connection items.
 */
export function parseCsvConnections(raw: string): ParsedConnectionItem[] {
  if (!raw || !raw.trim()) return []
  const clean = raw.replace(/\r\n/g, '\n').replace(/\r/g, '\n').trim()
  const lines = clean.split('\n').filter((l) => l.trim().length > 0)
  if (lines.length < 2) return []

  const firstLine = lines[0]
  const delimiter = firstLine.includes(';') && !firstLine.includes(',') ? ';' : ','
  const headers = parseCsvLine(firstLine, delimiter).map((h) => h.toLowerCase().replace(/[\s_-]+/g, ''))

  const getIdx = (...names: string[]) => {
    return headers.findIndex((h) => names.some((n) => h.includes(n)))
  }

  const nameIdx = getIdx('name', 'title')
  const hostIdx = getIdx('host', 'ip', 'server', 'hostname')
  const portIdx = getIdx('port')
  const userIdx = getIdx('user', 'username')
  const passIdx = getIdx('pass', 'password')
  const groupIdx = getIdx('group', 'folder', 'category')
  const typeIdx = getIdx('type')
  const dbIdx = getIdx('database', 'db')
  const dbHostIdx = getIdx('dbhost')
  const dbPortIdx = getIdx('dbport')
  const dbUserIdx = getIdx('dbuser')
  const dbPassIdx = getIdx('dbpass', 'dbpassword')
  const pathIdx = getIdx('remotepath', 'path', 'dir')
  const branchIdx = getIdx('branch')
  const notesIdx = getIdx('note', 'desc')

  const results: ParsedConnectionItem[] = []

  for (let i = 1; i < lines.length; i++) {
    const cols = parseCsvLine(lines[i], delimiter)
    if (!cols.length) continue

    const host = (hostIdx !== -1 ? cols[hostIdx] : '') || (dbHostIdx !== -1 ? cols[dbHostIdx] : '') || '127.0.0.1'
    const port = Number(portIdx !== -1 ? cols[portIdx] : '') || 22
    const user = (userIdx !== -1 ? cols[userIdx] : '') || 'root'
    const name = (nameIdx !== -1 ? cols[nameIdx] : '') || `${user}@${host}`
    const group = (groupIdx !== -1 ? cols[groupIdx] : '') || 'Imported'
    const password = passIdx !== -1 ? cols[passIdx] : ''
    const database = dbIdx !== -1 ? cols[dbIdx] : ''
    const dbHost = (dbHostIdx !== -1 ? cols[dbHostIdx] : '') || host
    const dbPort = Number(dbPortIdx !== -1 ? cols[dbPortIdx] : '') || 3306
    const dbUser = (dbUserIdx !== -1 ? cols[dbUserIdx] : '') || user
    const dbPassword = (dbPassIdx !== -1 ? cols[dbPassIdx] : '') || password
    const remotePath = pathIdx !== -1 ? cols[pathIdx] : ''
    const branch = (branchIdx !== -1 ? cols[branchIdx] : '') || 'main'
    const notes = notesIdx !== -1 ? cols[notesIdx] : ''
    const type = (typeIdx !== -1 ? cols[typeIdx] : '') || 'MariaDB'

    results.push({
      name,
      host,
      port,
      user,
      password,
      savePassword: true,
      group,
      type,
      color: 'blue',
      database,
      notes,
      remotePath,
      branch,
      dbHost,
      dbPort,
      dbUser,
      dbPassword,
      dbSavePassword: true,
      selected: true
    })
  }

  return results
}

/**
 * Resolves folder hierarchy map from DBeaver's `folders` root definition.
 */
function buildDBeaverFolderMap(foldersObj: any): Map<string, string> {
  const folderMap = new Map<string, string>()
  if (!foldersObj || typeof foldersObj !== 'object') return folderMap

  for (const [folderId, folderVal] of Object.entries(foldersObj as Record<string, any>)) {
    if (folderVal && typeof folderVal === 'object') {
      const displayName = folderVal.name ? String(folderVal.name).trim() : folderId
      folderMap.set(folderId, displayName)
    } else {
      folderMap.set(folderId, String(folderId).trim())
    }
  }

  for (const [folderId, folderVal] of Object.entries(foldersObj as Record<string, any>)) {
    if (folderVal && typeof folderVal === 'object' && folderVal.parent) {
      const parentId = String(folderVal.parent).trim()
      const parentName = folderMap.get(parentId) || parentId
      const currentName =
        folderMap.get(folderId) || (folderVal.name ? String(folderVal.name).trim() : folderId)
      if (parentName && currentName && parentName !== currentName) {
        folderMap.set(folderId, `${parentName}/${currentName}`)
      }
    }
  }

  return folderMap
}

/**
 * Extracts all folder/group names defined in DBeaver project data.
 */
export function extractDBeaverFolders(raw: string): string[] {
  if (!raw || !raw.trim() || raw.startsWith('PK')) return []
  try {
    const data = JSON.parse(raw.trim())
    const folders: string[] = []
    const folderMap = buildDBeaverFolderMap(data.folders)

    for (const name of folderMap.values()) {
      const cleaned = name.replace(/^\/+|\/+$/g, '').trim()
      if (cleaned && !folders.includes(cleaned)) {
        folders.push(cleaned)
      }
    }

    const conns = data.connections || data
    if (conns && typeof conns === 'object') {
      for (const item of Object.values(conns as Record<string, any>)) {
        if (!item || typeof item !== 'object') continue
        let f = ''
        if (item.folder) {
          const rawF = String(item.folder).trim()
          f = folderMap.get(rawF) || rawF
        } else if (Array.isArray(item.folders) && item.folders.length > 0) {
          f = item.folders
            .map((k: any) => folderMap.get(String(k).trim()) || String(k).trim())
            .filter(Boolean)
            .join('/')
        }
        f = f.replace(/^\/+|\/+$/g, '').trim()
        if (f && !folders.includes(f)) {
          folders.push(f)
        }
      }
    }

    return folders
  } catch {
    return []
  }
}

function findConnectionCredentials(
  credentials: Record<string, any> | undefined,
  connId: string,
  altIds: (string | undefined)[]
): Record<string, any> {
  if (!credentials || typeof credentials !== 'object') return {}

  const idsToTry = [connId, ...altIds].filter((x): x is string => Boolean(x && typeof x === 'string'))

  for (const id of idsToTry) {
    if (credentials[id] && typeof credentials[id] === 'object') {
      return credentials[id]
    }
  }

  for (const subVal of Object.values(credentials)) {
    if (subVal && typeof subVal === 'object') {
      for (const id of idsToTry) {
        if (subVal[id] && typeof subVal[id] === 'object') {
          return subVal[id]
        }
      }
    }
  }

  const lowerIds = idsToTry.map((i) => i.toLowerCase())
  for (const [k, v] of Object.entries(credentials)) {
    if (lowerIds.includes(k.toLowerCase()) && v && typeof v === 'object') {
      return v
    }
    if (v && typeof v === 'object') {
      for (const [innerK, innerV] of Object.entries(v)) {
        if (lowerIds.includes(innerK.toLowerCase()) && innerV && typeof innerV === 'object') {
          return innerV
        }
      }
    }
  }

  return {}
}

/**
 * Parses DBeaver's `data-sources.json` export or configuration file.
 */
export function parseDBeaverConnections(
  raw: string,
  credentials?: Record<string, any>
): ParsedConnectionItem[] {
  if (!raw || !raw.trim()) return []
  if (raw.startsWith('PK')) {
    throw new Error(
      'File ini merupakan arsip biner DBeaver (.dbp). Silakan pilih file melalui tombol Browse untuk membacanya.'
    )
  }
  const data = JSON.parse(raw.trim())
  const conns = data.connections || data
  if (!conns || typeof conns !== 'object') return []

  const folderMap = buildDBeaverFolderMap(data.folders)
  const results: ParsedConnectionItem[] = []

  for (const [key, item] of Object.entries(conns as Record<string, any>)) {
    if (!item || typeof item !== 'object') continue

    const config = item.configuration || {}

    // Check item.handlers, config.handlers, and item.network
    const handlers = item.handlers || config.handlers || item.network || {}
    const sshTunnelNode =
      handlers.ssh_tunnel ||
      handlers['ssh-tunnel'] ||
      handlers.ssh ||
      handlers['network/ssh_tunnel'] ||
      {}
    const sshProps =
      sshTunnelNode.properties ||
      sshTunnelNode.parameters ||
      sshTunnelNode.configuration ||
      sshTunnelNode ||
      {}

    const isSshEnabled = Boolean(
      (sshTunnelNode.enabled === true ||
        (sshTunnelNode.enabled !== false && sshTunnelNode.type === 'TUNNEL')) &&
        (sshProps.host || sshProps.hostname || sshProps.server)
    )

    // Name & Folder
    const name = item.name || config.database || key

    let folder = ''
    if (item.folder) {
      const rawF = String(item.folder).trim()
      folder = folderMap.get(rawF) || rawF
    } else if (Array.isArray(item.folders) && item.folders.length > 0) {
      folder = item.folders
        .map((k: any) => folderMap.get(String(k).trim()) || String(k).trim())
        .filter(Boolean)
        .join('/')
    }
    folder = folder.replace(/^\/+|\/+$/g, '').trim()
    if (!folder) {
      folder = 'DBeaver'
    }

    // Match credentials from decrypted credentials-config.json
    const credObj = findConnectionCredentials(credentials, key, [item.id, name, config.database])

    // Find SSH Credentials in credentials-config.json
    let sshCred =
      credObj['network/ssh_tunnel'] ||
      credObj['#network/ssh_tunnel'] ||
      credObj['#ssh_tunnel'] ||
      credObj['ssh_tunnel'] ||
      credObj['network/ssh'] ||
      credObj['#network/ssh'] ||
      credObj['#ssh'] ||
      credObj['ssh'] ||
      credObj.auth?.ssh_tunnel ||
      credObj.auth?.['network/ssh_tunnel'] ||
      credObj.network?.ssh_tunnel ||
      {}

    if (!sshCred.user && !sshCred.password) {
      const sshKey = Object.keys(credObj).find((k) => k.toLowerCase().includes('ssh'))
      if (sshKey && typeof credObj[sshKey] === 'object') {
        sshCred = credObj[sshKey]
      }
    }

    // Find Database Credentials in credentials-config.json
    let dbCred =
      credObj['#connection'] ||
      credObj['connection'] ||
      credObj['#auth'] ||
      credObj['auth'] ||
      credObj['database'] ||
      {}

    if (!dbCred.user && !dbCred.password) {
      const connKey = Object.keys(credObj).find((k) => {
        const l = k.toLowerCase()
        return (l.includes('connection') || l.includes('auth')) && !l.includes('ssh')
      })
      if (connKey && typeof credObj[connKey] === 'object') {
        dbCred = credObj[connKey]
      }
    }

    // Database attributes & credentials
    const dbHost = String(config.host || '127.0.0.1')
    const dbPort = Number(config.port) || 3306
    const dbUser = String(
      dbCred.user ||
        dbCred.userName ||
        dbCred['user-name'] ||
        credObj.user ||
        config.user ||
        config.userName ||
        config['user-name'] ||
        'root'
    )
    const dbPassword = String(
      dbCred.password ||
        dbCred['user-password'] ||
        credObj.password ||
        config.password ||
        ''
    )
    const database = String(config.database || '')

    // SSH Host & Port
    const host =
      isSshEnabled || sshProps.host
        ? String(sshProps.host || sshProps.hostname || sshProps.server || config.host || '127.0.0.1')
        : String(config.host || '127.0.0.1')
    const port =
      isSshEnabled || sshProps.port ? Number(sshProps.port) || 22 : 22

    // SSH User & Password
    let user = 'root'
    let password = ''

    if (isSshEnabled || sshProps.host) {
      user = String(
        sshCred.user ||
          sshCred.userName ||
          sshCred['user-name'] ||
          sshProps.user ||
          sshProps.userName ||
          sshProps['user-name'] ||
          'root'
      )
      password = String(
        sshCred.password ||
          sshCred['user-password'] ||
          sshProps.password ||
          sshProps['user-password'] ||
          ''
      )
    } else {
      user = String(
        sshCred.user ||
          sshProps.user ||
          (dbUser !== 'root' ? dbUser : 'root')
      )
      password = String(
        sshCred.password ||
          sshProps.password ||
          dbPassword ||
          ''
      )
    }

    // Determine type
    const provider = String(item.provider || item.driver || '').toLowerCase()
    let type = 'MariaDB'
    if (provider.includes('postgres')) type = 'PostgreSQL'
    else if (provider.includes('sqlite')) type = 'SQLite'
    else if (provider.includes('mysql')) type = 'MySQL'
    else if (provider.includes('oracle')) type = 'Oracle'
    else if (provider.includes('sqlserver') || provider.includes('mssql')) type = 'SQL Server'

    results.push({
      name,
      host,
      port,
      user,
      password,
      savePassword: Boolean(password),
      group: folder || 'DBeaver',
      type,
      color: 'blue',
      database,
      notes: item.description || `Imported from DBeaver (${provider})`,
      remotePath: '',
      branch: 'main',
      dbHost,
      dbPort,
      dbUser,
      dbPassword,
      dbSavePassword: Boolean(dbPassword),
      selected: true
    })
  }

  return results
}

/**
 * Parses DataGrip / IntelliJ XML dataSources.xml or raw JDBC URL lines.
 */
export function parseDataGripConnections(raw: string): ParsedConnectionItem[] {
  if (!raw || !raw.trim()) return []
  const text = raw.trim()
  const results: ParsedConnectionItem[] = []

  // Case 1: XML Format (<data-source ...>)
  const dataSourceRegex = /<data-source[\s\S]*?<\/data-source>/gi
  const matches = text.match(dataSourceRegex)

  if (matches && matches.length > 0) {
    for (const block of matches) {
      const nameMatch = block.match(/name="([^"]+)"/i)
      const name = nameMatch ? nameMatch[1] : 'DataGrip Source'

      const urlMatch = block.match(/<jdbc-url>([^<]+)<\/jdbc-url>/i)
      const userMatch = block.match(/<user-name>([^<]+)<\/user-name>/i)
      const sshHostMatch = block.match(/<ssh-tunnel[^>]*host="([^"]+)"/i) || block.match(/sshTunnelHost="([^"]+)"/i)
      const sshPortMatch = block.match(/<ssh-tunnel[^>]*port="([^"]+)"/i)
      const sshUserMatch = block.match(/<ssh-tunnel[^>]*user="([^"]+)"/i)

      let dbHost = '127.0.0.1'
      let dbPort = 3306
      let database = ''
      let type = 'MariaDB'

      if (urlMatch) {
        const url = urlMatch[1]
        // jdbc:mysql://host:port/database
        const parts = url.match(/jdbc:([a-zA-Z0-9_-]+):\/\/([^:/]+)(?::(\d+))?(?:\/([^?#]+))?/i)
        if (parts) {
          const proto = parts[1].toLowerCase()
          if (proto.includes('postgres')) type = 'PostgreSQL'
          else if (proto.includes('mysql')) type = 'MySQL'
          else if (proto.includes('sqlite')) type = 'SQLite'

          dbHost = parts[2] || '127.0.0.1'
          dbPort = parts[3] ? Number(parts[3]) : proto.includes('postgres') ? 5432 : 3306
          database = parts[4] || ''
        }
      }

      const host = sshHostMatch ? sshHostMatch[1] : dbHost
      const port = sshPortMatch ? Number(sshPortMatch[1]) : 22
      const user = (sshUserMatch ? sshUserMatch[1] : userMatch ? userMatch[1] : 'root') || 'root'
      const dbUser = userMatch ? userMatch[1] : 'root'

      results.push({
        name,
        host,
        port,
        user,
        password: '',
        savePassword: false,
        group: 'DataGrip',
        type,
        color: 'blue',
        database,
        notes: `Imported from DataGrip`,
        remotePath: '',
        branch: 'main',
        dbHost,
        dbPort,
        dbUser,
        dbPassword: '',
        dbSavePassword: false,
        selected: true
      })
    }
    return results
  }

  // Case 2: Raw JDBC URL or lines
  const lines = text.split('\n').filter((l) => l.trim().length > 0)
  for (const line of lines) {
    if (line.startsWith('jdbc:') || line.includes('://')) {
      const parts = line.match(/(?:jdbc:)?([a-zA-Z0-9_-]+):\/\/([^:/]+)(?::(\d+))?(?:\/([^?#\s]+))?/i)
      if (parts) {
        const proto = parts[1].toLowerCase()
        const dbHost = parts[2] || '127.0.0.1'
        const dbPort = parts[3] ? Number(parts[3]) : 3306
        const database = parts[4] || ''

        results.push({
          name: database ? `${database} (${dbHost})` : dbHost,
          host: dbHost,
          port: 22,
          user: 'root',
          password: '',
          savePassword: false,
          group: 'DataGrip',
          type: proto.includes('postgres') ? 'PostgreSQL' : 'MariaDB',
          color: 'blue',
          database,
          notes: line,
          remotePath: '',
          branch: 'main',
          dbHost,
          dbPort,
          dbUser: 'root',
          dbPassword: '',
          dbSavePassword: false,
          selected: true
        })
      }
    }
  }

  return results
}

/**
 * Exports connections to formatted JSON string.
 */
export function exportConnectionsToJson(connections: HostItem[], includePasswords = true): string {
  const data = connections.map((c) => ({
    name: c.name,
    host: c.ip,
    port: c.port || 22,
    user: c.user || 'root',
    password: includePasswords ? c.password || '' : undefined,
    savePassword: c.savePassword !== false,
    group: c.group || 'Default',
    type: c.type || 'MariaDB',
    color: c.color || 'blue',
    database: c.database || '',
    notes: c.notes || '',
    remotePath: c.remotePath || '',
    branch: c.branch || 'main',
    dbHost: c.dbHost || c.ip,
    dbPort: c.dbPort || 3306,
    dbUser: c.dbUser || c.user || 'root',
    dbPassword: includePasswords ? c.dbPassword || '' : undefined,
    dbSavePassword: c.dbSavePassword !== false,
    isProduction: Boolean(c.isProduction)
  }))

  return JSON.stringify(data, null, 2)
}

/**
 * Exports connections to CSV string.
 */
export function exportConnectionsToCsv(connections: HostItem[], includePasswords = true): string {
  const headers = [
    'Name',
    'Host',
    'Port',
    'User',
    'Password',
    'Group',
    'Type',
    'RemotePath',
    'Branch',
    'Database',
    'DbHost',
    'DbPort',
    'DbUser',
    'DbPassword',
    'Notes'
  ]

  const escapeCol = (val: any) => {
    const s = String(val !== undefined && val !== null ? val : '')
    if (s.includes(',') || s.includes('"') || s.includes('\n')) {
      return `"${s.replace(/"/g, '""')}"`
    }
    return s
  }

  const rows = connections.map((c) => {
    return [
      escapeCol(c.name),
      escapeCol(c.ip),
      escapeCol(c.port || 22),
      escapeCol(c.user || 'root'),
      escapeCol(includePasswords ? c.password || '' : ''),
      escapeCol(c.group || 'Default'),
      escapeCol(c.type || 'MariaDB'),
      escapeCol(c.remotePath || ''),
      escapeCol(c.branch || 'main'),
      escapeCol(c.database || ''),
      escapeCol(c.dbHost || c.ip),
      escapeCol(c.dbPort || 3306),
      escapeCol(c.dbUser || c.user || 'root'),
      escapeCol(includePasswords ? c.dbPassword || '' : ''),
      escapeCol(c.notes || '')
    ].join(',')
  })

  return [headers.join(','), ...rows].join('\n')
}

