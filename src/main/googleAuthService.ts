import http from 'http'
import { shell } from 'electron'

const GOOGLE_CLIENT_ID = '764086051850-6qr4p6gpi6hn506pt8ejuq83di341hur.apps.googleusercontent.com'
const GOOGLE_CLIENT_SECRET = 'd-FL95Q19q7MQmFpd7hHD0Ty'
const SCOPES = [
  'https://www.googleapis.com/auth/cloud-platform',
  'https://www.googleapis.com/auth/userinfo.email',
  'openid'
].join(' ')

export interface GoogleAuthResult {
  success: boolean
  token?: string
  refreshToken?: string
  email?: string
  error?: string
}

export const googleAuthService = {
  async signIn(): Promise<GoogleAuthResult> {
    return new Promise((resolve) => {
      let isResolved = false
      const timeoutId = setTimeout(() => {
        if (!isResolved) {
          isResolved = true
          try { server.close() } catch {}
          resolve({ success: false, error: 'Authentication timed out. Please try again.' })
        }
      }, 180000) // 3 minutes timeout

      const server = http.createServer(async (req, res) => {
        try {
          const reqUrl = new URL(req.url || '/', `http://${req.headers.host || '127.0.0.1'}`)
          if (!reqUrl.pathname.startsWith('/callback')) {
            res.writeHead(404)
            res.end()
            return
          }

          const code = reqUrl.searchParams.get('code')
          const error = reqUrl.searchParams.get('error')

          if (error || !code) {
            res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' })
            res.end(`
              <!DOCTYPE html><html><body style="font-family:system-ui;background:#181A1F;color:#fff;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;">
                <div style="background:#20242D;padding:32px;border-radius:12px;text-align:center;border:1px solid #EF4444;">
                  <h2 style="color:#EF4444;margin:0 0 8px;">Login Failed</h2>
                  <p style="color:#94A3B8;margin:0;">${error || 'No authorization code received'}. You can close this window.</p>
                </div>
              </body></html>
            `)
            if (!isResolved) {
              isResolved = true
              clearTimeout(timeoutId)
              server.close()
              resolve({ success: false, error: error || 'Authorization was cancelled.' })
            }
            return
          }

          // Exchange authorization code for tokens
          const address = server.address()
          const port = address && typeof address === 'object' ? address.port : 0
          const redirectUri = `http://127.0.0.1:${port}/callback`

          const tokenRes = await fetch('https://oauth2.googleapis.com/token', {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: new URLSearchParams({
              code,
              client_id: GOOGLE_CLIENT_ID,
              client_secret: GOOGLE_CLIENT_SECRET,
              redirect_uri: redirectUri,
              grant_type: 'authorization_code'
            })
          })

          const tokenData = await tokenRes.json()

          if (!tokenRes.ok || !tokenData.access_token) {
            res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' })
            res.end(`
              <!DOCTYPE html><html><body style="font-family:system-ui;background:#181A1F;color:#fff;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;">
                <div style="background:#20242D;padding:32px;border-radius:12px;text-align:center;border:1px solid #EF4444;">
                  <h2 style="color:#EF4444;margin:0 0 8px;">Token Error</h2>
                  <p style="color:#94A3B8;margin:0;">${tokenData.error_description || tokenData.error || 'Failed to retrieve access token'}</p>
                </div>
              </body></html>
            `)
            if (!isResolved) {
              isResolved = true
              clearTimeout(timeoutId)
              server.close()
              resolve({ success: false, error: tokenData.error_description || tokenData.error || 'Token exchange failed' })
            }
            return
          }

          // Fetch user profile email
          let email = ''
          try {
            const userRes = await fetch('https://www.googleapis.com/oauth2/v2/userinfo', {
              headers: { Authorization: `Bearer ${tokenData.access_token}` }
            })
            if (userRes.ok) {
              const userData = await userRes.json()
              email = userData.email || ''
            }
          } catch {}

          // Send success page to browser
          res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' })
          res.end(`
            <!DOCTYPE html><html><head><title>Connected to Pullman</title></head>
            <body style="font-family:system-ui,-apple-system,sans-serif;background:#0F1117;color:#F1F5F9;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;">
              <div style="background:#181A20;padding:36px;border-radius:16px;text-align:center;max-width:400px;border:1px solid #2D3342;box-shadow:0 12px 32px rgba(0,0,0,0.6);">
                <div style="width:48px;height:48px;background:rgba(16,185,129,0.15);border-radius:50%;display:flex;align-items:center;justify-content:center;margin:0 auto 16px;color:#10B981;font-size:24px;">✓</div>
                <h2 style="color:#F1F5F9;margin:0 0 8px;font-size:18px;font-weight:600;">Connected to Pullman!</h2>
                <p style="color:#94A3B8;margin:0 0 20px;font-size:13px;line-height:1.5;">${email ? `Signed in as <strong>${email}</strong>.<br>` : ''}You can close this tab and return to Pullman app.</p>
                <div style="font-size:11px;color:#64748B;">Pullman SFTP & Cloud Editor</div>
              </div>
            </body></html>
          `)

          if (!isResolved) {
            isResolved = true
            clearTimeout(timeoutId)
            setTimeout(() => { try { server.close() } catch {} }, 1000)
            resolve({
              success: true,
              token: tokenData.access_token,
              refreshToken: tokenData.refresh_token,
              email
            })
          }
        } catch (err) {
          if (!isResolved) {
            isResolved = true
            clearTimeout(timeoutId)
            try { server.close() } catch {}
            resolve({ success: false, error: err instanceof Error ? err.message : String(err) })
          }
        }
      })

      server.listen(0, '127.0.0.1', () => {
        const addr = server.address()
        const port = addr && typeof addr === 'object' ? addr.port : 0
        const redirectUri = `http://127.0.0.1:${port}/callback`
        const authUrl = `https://accounts.google.com/o/oauth2/v2/auth?client_id=${encodeURIComponent(GOOGLE_CLIENT_ID)}&redirect_uri=${encodeURIComponent(redirectUri)}&response_type=code&scope=${encodeURIComponent(SCOPES)}&access_type=offline&prompt=consent`
        shell.openExternal(authUrl)
      })

      server.on('error', (err) => {
        if (!isResolved) {
          isResolved = true
          clearTimeout(timeoutId)
          resolve({ success: false, error: `Failed to start local server: ${err.message}` })
        }
      })
    })
  },

  async refreshToken(refreshToken: string): Promise<{ success: boolean; token?: string; error?: string }> {
    try {
      const res = await fetch('https://oauth2.googleapis.com/token', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({
          client_id: GOOGLE_CLIENT_ID,
          client_secret: GOOGLE_CLIENT_SECRET,
          refresh_token: refreshToken,
          grant_type: 'refresh_token'
        })
      })
      const data = await res.json()
      if (res.ok && data.access_token) {
        return { success: true, token: data.access_token }
      }
      return { success: false, error: data.error_description || data.error || 'Failed to refresh token' }
    } catch (err) {
      return { success: false, error: err instanceof Error ? err.message : String(err) }
    }
  }
}

