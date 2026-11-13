import http from 'http'
import https from 'https'
import { URL } from 'url'

export interface RedmineRequestPayload {
  url: string
  method?: string
  headers?: Record<string, string>
  body?: string
  bodyBase64?: string
  responseType?: 'json' | 'text' | 'dataUrl'
}

export interface RedmineResponseResult {
  ok: boolean
  status: number
  statusText?: string
  data?: any
  error?: string
}

export const redmineService = {
  async request(payload: RedmineRequestPayload, redirectCount = 0): Promise<RedmineResponseResult> {
    if (redirectCount > 3) {
      return { ok: false, status: 310, error: 'Too many redirects from Redmine server.' }
    }

    let targetUrl = payload.url.trim()
    if (!targetUrl.startsWith('http://') && !targetUrl.startsWith('https://')) {
      targetUrl = `https://${targetUrl}`
    }

    let parsedUrl: URL
    try {
      parsedUrl = new URL(targetUrl)
    } catch {
      return { ok: false, status: 400, error: `Invalid Redmine URL: ${targetUrl}` }
    }

    const isHttps = parsedUrl.protocol === 'https:'
    const client = isHttps ? https : http

    return new Promise((resolve) => {
      const headers: Record<string, string> = {
        Accept: payload.responseType === 'dataUrl' ? 'image/*, */*' : 'application/json, text/plain, */*',
        'User-Agent': 'Pullman-SSH/2.0.0 (RedmineClient)',
        ...(payload.headers || {})
      }

      if (payload.headers?.['X-Redmine-API-Key'] && !headers['Authorization']) {
        try {
          headers['Authorization'] = `Basic ${Buffer.from(`${payload.headers['X-Redmine-API-Key']}:x`).toString('base64')}`
        } catch {}
      }

      let bodyBuffer: Buffer | null = null
      if (payload.bodyBase64) {
        bodyBuffer = Buffer.from(payload.bodyBase64, 'base64')
        headers['Content-Type'] = headers['Content-Type'] || 'application/octet-stream'
        headers['Content-Length'] = bodyBuffer.length.toString()
      } else if (payload.body) {
        bodyBuffer = Buffer.from(payload.body, 'utf-8')
        headers['Content-Type'] = headers['Content-Type'] || 'application/json'
        headers['Content-Length'] = bodyBuffer.length.toString()
      }

      const reqOptions: https.RequestOptions = {
        protocol: parsedUrl.protocol,
        hostname: parsedUrl.hostname,
        port: parsedUrl.port || (isHttps ? 443 : 80),
        path: `${parsedUrl.pathname}${parsedUrl.search}`,
        method: payload.method || 'GET',
        headers,
        rejectUnauthorized: false, // allow intranet self-signed certificates
        timeout: 20000
      }

      const req = client.request(reqOptions, (res) => {
        const statusCode = res.statusCode || 0
        const statusText = res.statusMessage || ''

        // Handle HTTP Redirects (301, 302, 307, 308)
        if ([301, 302, 303, 307, 308].includes(statusCode) && res.headers.location) {
          const redirectLocation = new URL(res.headers.location, parsedUrl).toString()
          const nextHeaders = { ...headers }
          if (res.headers['set-cookie']) {
            const cookieStr = Array.isArray(res.headers['set-cookie'])
              ? res.headers['set-cookie'].map((c) => c.split(';')[0]).join('; ')
              : String(res.headers['set-cookie']).split(';')[0]
            nextHeaders['Cookie'] = cookieStr
          }
          return resolve(
            redmineService.request(
              { ...payload, url: redirectLocation, headers: nextHeaders },
              redirectCount + 1
            )
          )
        }

        const chunks: Buffer[] = []
        res.on('data', (chunk) => chunks.push(chunk))
        res.on('end', () => {
          const buffer = Buffer.concat(chunks)
          const contentType = (res.headers['content-type'] || '').toLowerCase()
          const isImageContentType = contentType.startsWith('image/')
          const rawPrefix = buffer.slice(0, 100).toString('utf-8').trim().toLowerCase()
          const isHtml =
            contentType.includes('text/html') ||
            rawPrefix.startsWith('<!doctype') ||
            rawPrefix.startsWith('<html')

          let parsedData: any = null

          if (payload.responseType === 'dataUrl' || isImageContentType) {
            if (isHtml) {
              return resolve({
                ok: false,
                status: statusCode >= 200 && statusCode < 300 ? 401 : statusCode,
                error: 'Received HTML page instead of image data. Authentication required.'
              })
            }

            let mime = isImageContentType ? contentType.split(';')[0].trim() : ''
            if (!mime || mime === 'application/octet-stream') {
              const pathname = parsedUrl.pathname.toLowerCase()
              if (pathname.endsWith('.jpg') || pathname.endsWith('.jpeg')) mime = 'image/jpeg'
              else if (pathname.endsWith('.gif')) mime = 'image/gif'
              else if (pathname.endsWith('.webp')) mime = 'image/webp'
              else if (pathname.endsWith('.svg')) mime = 'image/svg+xml'
              else if (pathname.endsWith('.bmp')) mime = 'image/bmp'
              else mime = 'image/png'
            }

            parsedData = `data:${mime};base64,${buffer.toString('base64')}`
          } else {
            const raw = buffer.toString('utf-8')
            try {
              parsedData = JSON.parse(raw)
            } catch {
              parsedData = raw
            }
          }

          const ok = statusCode >= 200 && statusCode < 300
          if (!ok) {
            let errorMsg = `HTTP ${statusCode} ${statusText}`
            if (statusCode === 401) {
              errorMsg = '401 Unauthorized: Invalid Redmine API Key.'
            } else if (statusCode === 403) {
              errorMsg = '403 Forbidden: Please enable "REST web service" in Redmine: Administration > Settings > API.'
            } else if (statusCode === 404) {
              errorMsg = `404 Not Found: Check your Redmine URL path.`
            } else if (typeof parsedData === 'object' && parsedData?.errors) {
              errorMsg = Array.isArray(parsedData.errors) ? parsedData.errors.join(', ') : JSON.stringify(parsedData.errors)
            }
            return resolve({ ok: false, status: statusCode, statusText, data: parsedData, error: errorMsg })
          }

          return resolve({ ok: true, status: statusCode, statusText, data: parsedData })
        })
      })

      req.on('timeout', () => {
        req.destroy()
        resolve({ ok: false, status: 408, error: 'Connection to Redmine server timed out (20s).' })
      })

      req.on('error', (err: any) => {
        let message = err.message || 'Connection error'
        if (err.code === 'ECONNREFUSED') {
          message = `Connection refused at ${parsedUrl.hostname}:${reqOptions.port}. Is the server running?`
        } else if (err.code === 'ENOTFOUND') {
          message = `Host not found: ${parsedUrl.hostname}. Please verify the URL.`
        } else if (err.code === 'DEPTH_ZERO_SELF_SIGNED_CERT') {
          message = 'Self-signed certificate detected.'
        }
        resolve({ ok: false, status: 0, error: message })
      })

      if (bodyBuffer) {
        req.write(bodyBuffer)
      }
      req.end()
    })
  }
}

