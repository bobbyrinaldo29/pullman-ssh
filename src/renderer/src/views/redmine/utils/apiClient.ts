import type { RedmineConfig } from '../types'

export interface RedmineApiCallOptions {
  method?: string
  body?: unknown
  bodyBase64?: string
  responseType?: 'json' | 'text' | 'dataUrl'
  headers?: Record<string, string>
}

export async function callRedmineEndpoint(
  config: RedmineConfig,
  endpoint: string,
  options?: RedmineApiCallOptions
): Promise<{ ok: boolean; status: number; data?: any; error?: string }> {
  if (!config.url || !config.apiKey) {
    return { ok: false, status: 401, error: 'Redmine URL and API Key are required.' }
  }

  let fullUrl = ''
  if (endpoint.startsWith('http://') || endpoint.startsWith('https://')) {
    const separator = endpoint.includes('?') ? '&' : '?'
    fullUrl = endpoint.includes('key=')
      ? endpoint
      : `${endpoint}${separator}key=${encodeURIComponent(config.apiKey)}`
  } else {
    let cleanBase = config.url.trim().replace(/\/$/, '')
    if (!cleanBase.startsWith('http://') && !cleanBase.startsWith('https://')) {
      cleanBase = `https://${cleanBase}`
    }
    const cleanEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`
    const separator = cleanEndpoint.includes('?') ? '&' : '?'
    fullUrl = `${cleanBase}${cleanEndpoint}${separator}key=${encodeURIComponent(config.apiKey)}`
  }

  const headers: Record<string, string> = {
    'X-Redmine-API-Key': config.apiKey,
    ...(options?.headers || {})
  }

  if (config.apiKey) {
    try {
      headers['Authorization'] = `Basic ${btoa(`${config.apiKey}:x`)}`
    } catch {
      // ignore btoa failures
    }
  }

  if (
    !options?.bodyBase64 &&
    options?.responseType !== 'dataUrl' &&
    options?.method &&
    options.method !== 'GET'
  ) {
    headers['Content-Type'] = headers['Content-Type'] || 'application/json'
  }

  if (options?.responseType === 'dataUrl') {
    headers['Accept'] = 'image/*, */*'
  }

  const bodyStr = options?.body ? JSON.stringify(options.body) : undefined

  if (window.api?.callRedmineApi) {
    return await window.api.callRedmineApi({
      url: fullUrl,
      method: options?.method || 'GET',
      headers,
      body: bodyStr,
      bodyBase64: options?.bodyBase64,
      responseType: options?.responseType
    })
  }

  try {
    const res = await fetch(fullUrl, {
      method: options?.method || 'GET',
      headers,
      body: bodyStr
    })
    const data = await res.json().catch(() => null)
    return { ok: res.ok, status: res.status, data }
  } catch {
    return {
      ok: false,
      status: 0,
      error:
        'Network error or CORS block. Please restart Pullman so the native Redmine bridge can connect.'
    }
  }
}
