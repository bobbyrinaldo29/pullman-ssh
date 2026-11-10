/**
 * Pure Web API ZIP extractor using built-in DecompressionStream('deflate-raw').
 * Works directly in browser/renderer context on raw ArrayBuffer/Uint8Array.
 */

const DBEAVER_DEFAULT_KEY_HEX = 'babb4a9f774ab853c96c2d653dfe544a'

/**
 * Decrypts DBeaver's AES-128-CBC credentials-config.json file.
 */
export async function decryptDBeaverCredentials(
  encryptedBytes: Uint8Array
): Promise<Record<string, any>> {
  try {
    const asText = new TextDecoder('utf-8').decode(encryptedBytes).trim()
    if (asText.startsWith('{')) {
      return JSON.parse(asText)
    }
  } catch {
    // continue
  }

  try {
    const keyBytes = new Uint8Array(16)
    for (let i = 0; i < 16; i++) {
      keyBytes[i] = parseInt(DBEAVER_DEFAULT_KEY_HEX.substr(i * 2, 2), 16)
    }
    const iv = new Uint8Array(16)

    const cryptoKey = await globalThis.crypto.subtle.importKey(
      'raw',
      keyBytes,
      { name: 'AES-CBC' },
      false,
      ['decrypt']
    )

    const decrypted = await globalThis.crypto.subtle.decrypt(
      { name: 'AES-CBC', iv },
      cryptoKey,
      new Uint8Array(encryptedBytes) as BufferSource
    )

    // DBeaver prepends a 16-byte binary header; extract exact JSON boundaries
    const textAll = new TextDecoder('utf-8').decode(new Uint8Array(decrypted))
    const firstBrace = textAll.indexOf('{')
    const lastBrace = textAll.lastIndexOf('}')
    if (firstBrace !== -1 && lastBrace !== -1 && lastBrace > firstBrace) {
      const jsonCandidate = textAll.substring(firstBrace, lastBrace + 1)
      return JSON.parse(jsonCandidate)
    }
    return {}
  } catch (err) {
    // If WebCrypto throws (e.g. padding mismatch), try fallback via main process if available
    try {
      if ((window as any)?.api?.decryptDBeaverCredentials) {
        return await (window as any).api.decryptDBeaverCredentials(Array.from(encryptedBytes))
      }
    } catch {
      // ignore
    }
    console.warn('Could not decrypt DBeaver credentials:', err)
    return {}
  }
}

export interface ExtractedDBeaverBundle {
  filename: string
  content: string
  credentials?: Record<string, any>
}

export async function extractDBeaverProjectFromUint8Array(
  bytes: Uint8Array
): Promise<ExtractedDBeaverBundle> {
  // If text (e.g. uncompressed raw json), decode directly
  if (bytes.length < 22 || bytes[0] !== 0x50 || bytes[1] !== 0x4b) {
    const text = new TextDecoder('utf-8').decode(bytes)
    return { filename: 'data-sources.json', content: text }
  }

  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength)

  // Find End of Central Directory (EOCD: 0x06054b50)
  let eocd = -1
  for (let i = bytes.length - 22; i >= 0; i--) {
    if (view.getUint32(i, true) === 0x06054b50) {
      eocd = i
      break
    }
  }

  if (eocd === -1) {
    throw new Error('File is not a valid ZIP / DBeaver project archive.')
  }

  const cdCount = view.getUint16(eocd + 10, true)
  const cdOffset = view.getUint32(eocd + 16, true)

  const files: Record<string, string> = {}
  const rawBytesMap: Record<string, Uint8Array> = {}
  let cur = cdOffset
  const textDecoder = new TextDecoder('utf-8')

  for (let i = 0; i < cdCount; i++) {
    if (cur + 46 > bytes.length) break
    if (view.getUint32(cur, true) !== 0x02014b50) break

    const compression = view.getUint16(cur + 10, true)
    const compSize = view.getUint32(cur + 20, true)
    const nameLen = view.getUint16(cur + 28, true)
    const extraLen = view.getUint16(cur + 30, true)
    const commLen = view.getUint16(cur + 32, true)
    const localHeaderOffset = view.getUint32(cur + 42, true)

    const nameBytes = bytes.subarray(cur + 46, cur + 46 + nameLen)
    const fileName = textDecoder.decode(nameBytes)
    cur += 46 + nameLen + extraLen + commLen

    if (fileName.endsWith('/') || fileName.endsWith('\\')) continue

    if (view.getUint32(localHeaderOffset, true) !== 0x04034b50) continue
    const locNameLen = view.getUint16(localHeaderOffset + 26, true)
    const locExtraLen = view.getUint16(localHeaderOffset + 28, true)
    const dataStart = localHeaderOffset + 30 + locNameLen + locExtraLen
    const compData = bytes.subarray(dataStart, dataStart + compSize)

    try {
      let decompressedBytes: Uint8Array
      if (compression === 0) {
        decompressedBytes = new Uint8Array(compData)
      } else if (compression === 8) {
        const ds = new DecompressionStream('deflate-raw')
        const writer = ds.writable.getWriter()
        writer.write(new Uint8Array(compData) as BufferSource)
        writer.close()
        const reader = ds.readable.getReader()
        const chunks: Uint8Array[] = []
        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          if (value) chunks.push(value)
        }

        let totalLen = 0
        for (const c of chunks) totalLen += c.length
        const merged = new Uint8Array(totalLen)
        let offset = 0
        for (const c of chunks) {
          merged.set(c, offset)
          offset += c.length
        }
        decompressedBytes = merged
      } else {
        continue
      }

      rawBytesMap[fileName] = decompressedBytes
      files[fileName] = textDecoder.decode(decompressedBytes)
    } catch {
      // Ignore individual corrupted file entry
    }
  }

  const keys = Object.keys(files)
  const targetKey =
    keys.find((k) => k.endsWith('data-sources.json')) ||
    keys.find((k) => k.toLowerCase().includes('data-sources') && k.endsWith('.json')) ||
    keys.find((k) => k.endsWith('.json') && files[k].includes('"connections"')) ||
    keys.find((k) => k.endsWith('dataSources.xml') || k.endsWith('data-sources.xml')) ||
    keys.find((k) => k.endsWith('.xml') && files[k].includes('<data-source')) ||
    keys.find((k) => k.endsWith('.json'))

  if (!targetKey || !files[targetKey]) {
    throw new Error('Tidak ditemukan data koneksi (data-sources.json) di dalam file project DBeaver (.dbp) ini.')
  }

  // Look for credentials-config.json and decrypt
  let credentials: Record<string, any> | undefined
  const credKey = Object.keys(rawBytesMap).find((k) => {
    const lower = k.toLowerCase()
    return (
      lower.endsWith('credentials-config.json') ||
      lower.endsWith('credentials.json') ||
      lower.endsWith('credentials-info.json') ||
      (lower.includes('credential') && lower.endsWith('.json'))
    )
  })
  if (credKey && rawBytesMap[credKey]) {
    credentials = await decryptDBeaverCredentials(rawBytesMap[credKey])
  }

  return { filename: targetKey, content: files[targetKey], credentials }
}
