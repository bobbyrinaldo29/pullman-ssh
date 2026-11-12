import { readFileSync } from 'fs'
import zlib from 'zlib'
import crypto from 'crypto'

export interface ExtractedDBeaverData {
  content: string
  detectedName: string
  credentials?: Record<string, any>
}

export function decryptDBeaverCredentialsNode(buf: Buffer): Record<string, any> {
  try {
    const asText = buf.toString('utf-8').trim()
    if (asText.startsWith('{')) {
      return JSON.parse(asText)
    }
  } catch {
    // continue
  }

  try {
    const key = Buffer.from('babb4a9f774ab853c96c2d653dfe544a', 'hex')
    const iv = Buffer.alloc(16, 0)
    const decipher = crypto.createDecipheriv('aes-128-cbc', key, iv)
    decipher.setAutoPadding(false)
    const decrypted = Buffer.concat([decipher.update(buf), decipher.final()])
    const textAll = decrypted.toString('utf-8')
    const firstBrace = textAll.indexOf('{')
    const lastBrace = textAll.lastIndexOf('}')
    if (firstBrace !== -1 && lastBrace !== -1 && lastBrace > firstBrace) {
      return JSON.parse(textAll.substring(firstBrace, lastBrace + 1))
    }
    return {}
  } catch (err) {
    console.warn('Could not decrypt DBeaver credentials in main process:', err)
    return {}
  }
}

/**
 * Extracts data-sources.json or data-sources.xml from a DBeaver project (.dbp, .zip)
 * or reads plain text json/xml file directly.
 */
export function extractDBeaverProjectFile(filePath: string): ExtractedDBeaverData {
  const buf = readFileSync(filePath)

  // 1. If not a ZIP archive, treat as plain text (raw data-sources.json or XML)
  if (buf.length < 22 || buf.readUInt32LE(0) !== 0x04034b50) {
    const text = buf.toString('utf-8')
    return {
      content: text,
      detectedName: filePath.split(/[/\\]/).pop() || 'data-sources.json'
    }
  }

  // 2. Parse ZIP archive via End of Central Directory (EOCD)
  let eocdOffset = -1
  for (let i = buf.length - 22; i >= 0; i--) {
    if (buf.readUInt32LE(i) === 0x06054b50) {
      eocdOffset = i
      break
    }
  }

  if (eocdOffset === -1) {
    throw new Error('Invalid or corrupted DBeaver project archive (.dbp/.zip).')
  }

  const cdCount = buf.readUInt16LE(eocdOffset + 10)
  const cdOffset = buf.readUInt32LE(eocdOffset + 16)

  const entries: Record<string, string> = {}
  const rawBuffers: Record<string, Buffer> = {}
  let currentOffset = cdOffset

  for (let i = 0; i < cdCount; i++) {
    if (currentOffset + 46 > buf.length) break
    if (buf.readUInt32LE(currentOffset) !== 0x02014b50) break

    const compression = buf.readUInt16LE(currentOffset + 10)
    const compressedSize = buf.readUInt32LE(currentOffset + 20)
    const fileNameLen = buf.readUInt16LE(currentOffset + 28)
    const extraLen = buf.readUInt16LE(currentOffset + 30)
    const commentLen = buf.readUInt16LE(currentOffset + 32)
    const localHeaderOffset = buf.readUInt32LE(currentOffset + 42)

    const fileName = buf.toString('utf-8', currentOffset + 46, currentOffset + 46 + fileNameLen)
    currentOffset += 46 + fileNameLen + extraLen + commentLen

    // Skip directories
    if (fileName.endsWith('/') || fileName.endsWith('\\')) continue

    // Read local file header to locate file data
    if (localHeaderOffset + 30 > buf.length) continue
    if (buf.readUInt32LE(localHeaderOffset) !== 0x04034b50) continue

    const localFileNameLen = buf.readUInt16LE(localHeaderOffset + 26)
    const localExtraLen = buf.readUInt16LE(localHeaderOffset + 28)
    const dataStart = localHeaderOffset + 30 + localFileNameLen + localExtraLen

    if (dataStart + compressedSize > buf.length) continue
    const compressedData = buf.subarray(dataStart, dataStart + compressedSize)

    try {
      let contentBuf: Buffer
      if (compression === 0) {
        contentBuf = compressedData
      } else if (compression === 8) {
        contentBuf = zlib.inflateRawSync(compressedData)
      } else {
        continue
      }
      rawBuffers[fileName] = contentBuf
      entries[fileName] = contentBuf.toString('utf-8')
    } catch {
      // Ignore corrupted individual entry
    }
  }

  const keys = Object.keys(entries)
  if (keys.length === 0) {
    throw new Error('DBeaver project archive (.dbp) is empty.')
  }

  // Prioritize data-sources.json or files with connection definitions
  const targetKey =
    keys.find((k) => k.endsWith('data-sources.json')) ||
    keys.find((k) => k.toLowerCase().includes('data-sources') && k.endsWith('.json')) ||
    keys.find((k) => k.endsWith('.json') && entries[k].includes('"connections"')) ||
    keys.find((k) => k.endsWith('dataSources.xml') || k.endsWith('data-sources.xml')) ||
    keys.find((k) => k.endsWith('.xml') && entries[k].includes('<data-source')) ||
    keys.find((k) => k.endsWith('.json'))

  if (targetKey && entries[targetKey]) {
    let credentials: Record<string, any> | undefined
    const credKey = Object.keys(rawBuffers).find((k) => {
      const lower = k.toLowerCase()
      return (
        lower.endsWith('credentials-config.json') ||
        lower.endsWith('credentials.json') ||
        lower.endsWith('credentials-info.json') ||
        (lower.includes('credential') && lower.endsWith('.json'))
      )
    })
    if (credKey && rawBuffers[credKey]) {
      credentials = decryptDBeaverCredentialsNode(rawBuffers[credKey])
    }

    return {
      content: entries[targetKey],
      detectedName: targetKey.split(/[/\\]/).pop() || 'data-sources.json',
      credentials
    }
  }

  throw new Error('Could not find data-sources.json or connection definitions inside this DBeaver project file.')
}

