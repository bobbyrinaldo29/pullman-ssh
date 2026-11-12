import { ParsedConnectionItem } from './connectionParsers'

function hexToUint8Array(hex: string): Uint8Array {
  const cleanHex = hex.replace(/[^0-9a-fA-F]/g, '')
  if (cleanHex.length % 2 !== 0) return new Uint8Array()
  const bytes = new Uint8Array(cleanHex.length / 2)
  for (let i = 0; i < cleanHex.length; i += 2) {
    bytes[i / 2] = parseInt(cleanHex.substring(i, i + 2), 16)
  }
  return bytes
}

/**
 * Decrypts Navicat 12/15/16/17 password encrypted with AES-128-CBC.
 */
export async function decryptNavicatPassword(encryptedHex: string): Promise<string> {
  if (!encryptedHex || !encryptedHex.trim()) return ''
  const hex = encryptedHex.trim()

  if (!/^[0-9a-fA-F]+$/.test(hex)) {
    return hex
  }

  try {
    const rawCipher = hexToUint8Array(hex)
    if (rawCipher.length >= 16 && rawCipher.length % 16 === 0) {
      const keyBytes = new TextEncoder().encode('libcckeylibcckey')
      const ivBytes = new TextEncoder().encode('libcciv libcciv ')

      const cryptoKey = await globalThis.crypto.subtle.importKey(
        'raw',
        keyBytes,
        { name: 'AES-CBC' },
        false,
        ['decrypt']
      )

      const decrypted = await globalThis.crypto.subtle.decrypt(
        { name: 'AES-CBC', iv: ivBytes },
        cryptoKey,
        rawCipher as unknown as BufferSource
      )

      const text = new TextDecoder().decode(decrypted)
      if (text && /^[\x20-\x7E\s]+$/.test(text)) {
        return text
      }
    }
  } catch {
    // ignore
  }

  return ''
}

function normalizeNavicatDbType(typeStr: string): string {
  const lower = (typeStr || '').toLowerCase()
  if (lower.includes('postgre')) return 'PostgreSQL'
  if (lower.includes('maria')) return 'MariaDB'
  if (lower.includes('mysql')) return 'MySQL'
  if (lower.includes('sqlite')) return 'SQLite'
  if (lower.includes('oracle')) return 'Oracle'
  if (lower.includes('mssql') || lower.includes('sqlserver')) return 'SQL Server'
  if (lower.includes('mongo')) return 'MongoDB'
  if (lower.includes('redis')) return 'Redis'
  return 'MariaDB'
}

/**
 * Parses Navicat export files (.ncx XML or JSON).
 */
export async function parseNavicatConnections(raw: string): Promise<ParsedConnectionItem[]> {
  if (!raw || !raw.trim()) return []
  const text = raw.trim()
  const results: ParsedConnectionItem[] = []

  // Case 1: JSON export (Navicat 16 / 17 or modern format)
  if (text.startsWith('{') || text.startsWith('[')) {
    try {
      const parsed = JSON.parse(text)
      const list: Record<string, unknown>[] = Array.isArray(parsed)
        ? parsed
        : Array.isArray(parsed.Connections)
          ? parsed.Connections
          : Array.isArray(parsed.connections)
            ? parsed.connections
            : []

      for (const item of list) {
        const name = String(item.ConnectionName || item.Name || item.name || 'Navicat Connection')
        const rawType = String(item.ConnType || item.Type || item.type || 'MYSQL')
        const type = normalizeNavicatDbType(rawType)

        const dbHost = String(item.Host || item.Server || item.host || '127.0.0.1')
        const dbPort = Number(item.Port || item.port) || (type === 'PostgreSQL' ? 5432 : 3306)
        const dbUser = String(item.UserName || item.User || item.user || 'root')
        const rawDbPass = String(item.Password || item.password || '')
        const dbPassword = await decryptNavicatPassword(rawDbPass)
        const database = String(item.Database || item.InitialDatabase || item.database || '')
        const group = String(item.Group || item.Category || item.group || 'Navicat')

        const sshHost = String(item.SSH_Host || item.SSHHost || item.ssh_host || '')
        const sshPort = Number(item.SSH_Port || item.SSHPort || item.ssh_port) || 22
        const sshUser = String(item.SSH_UserName || item.SSHUser || item.SSH_User || item.ssh_user || 'root')
        const rawSshPass = String(item.SSH_Password || item.SSHPassword || item.ssh_password || '')
        const sshPassword = await decryptNavicatPassword(rawSshPass)

        const hasSsh = Boolean(sshHost && sshHost.trim())
        const host = hasSsh ? sshHost.trim() : dbHost
        const port = hasSsh ? sshPort : 22
        const user = hasSsh ? sshUser : 'root'
        const password = hasSsh ? sshPassword : ''

        results.push({
          name,
          host,
          port,
          user,
          password,
          savePassword: Boolean(password),
          group,
          type,
          color: 'blue',
          database,
          notes: 'Imported from Navicat',
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

      if (results.length > 0) return results
    } catch {
      // not valid JSON, proceed to XML
    }
  }

  // Case 2: XML .ncx export format
  const connRegex = /<Connection[\s\S]*?(?:\/>|<\/Connection>)/gi
  const matches = text.match(connRegex) || []

  for (const block of matches) {
    const getVal = (attrName: string): string => {
      // 1. Try attribute: attrName="..."
      const attrMatch = block.match(new RegExp(`${attrName}\\s*=\\s*"([^"]*)"`, 'i'))
      if (attrMatch) return attrMatch[1]
      // 2. Try tag: <attrName>...</attrName>
      const tagMatch = block.match(new RegExp(`<${attrName}>([\\s\\S]*?)<\\/${attrName}>`, 'i'))
      if (tagMatch) return tagMatch[1].trim()
      return ''
    }

    const name = getVal('ConnectionName') || getVal('Name') || 'Navicat Connection'
    const rawType = getVal('ConnType') || getVal('Type') || 'MYSQL'
    const type = normalizeNavicatDbType(rawType)

    const dbHost = getVal('Host') || getVal('Server') || '127.0.0.1'
    const dbPort = Number(getVal('Port')) || (type === 'PostgreSQL' ? 5432 : 3306)
    const dbUser = getVal('UserName') || getVal('User') || 'root'
    const rawDbPass = getVal('Password')
    const dbPassword = await decryptNavicatPassword(rawDbPass)
    const database = getVal('Database') || getVal('InitialDatabase') || ''
    const group = getVal('Group') || getVal('Category') || 'Navicat'

    const sshHost = getVal('SSH_Host') || getVal('SSHHost')
    const sshPort = Number(getVal('SSH_Port') || getVal('SSHPort')) || 22
    const sshUser = getVal('SSH_UserName') || getVal('SSHUser') || getVal('SSH_User') || 'root'
    const rawSshPass = getVal('SSH_Password') || getVal('SSHPassword')
    const sshPassword = await decryptNavicatPassword(rawSshPass)

    const hasSsh = Boolean(sshHost && sshHost.trim())
    const host = hasSsh ? sshHost.trim() : dbHost
    const port = hasSsh ? sshPort : 22
    const user = hasSsh ? sshUser : 'root'
    const password = hasSsh ? sshPassword : ''

    results.push({
      name,
      host,
      port,
      user,
      password,
      savePassword: Boolean(password),
      group,
      type,
      color: 'blue',
      database,
      notes: 'Imported from Navicat',
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
