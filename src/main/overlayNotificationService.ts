import { BrowserWindow, screen } from 'electron'

export interface OverlayNotificationPayload {
  title: string
  subtitle?: string
  body: string
  tag?: string
  issueId?: number
  silent?: boolean
}

class OverlayNotificationService {
  private overlayWindow: BrowserWindow | null = null
  private dismissTimer: NodeJS.Timeout | null = null
  private onClickCallback: (() => void) | null = null

  public show(payload: OverlayNotificationPayload, onClick?: () => void): void {
    try {
      this.onClickCallback = onClick || null

      if (this.dismissTimer) {
        clearTimeout(this.dismissTimer)
        this.dismissTimer = null
      }

      // Detect display nearest to active mouse cursor, falling back to primary display
      let targetDisplay = screen.getPrimaryDisplay()
      try {
        const cursorPoint = screen.getCursorScreenPoint()
        const nearest = screen.getDisplayNearestPoint(cursorPoint)
        if (nearest) {
          targetDisplay = nearest
        }
      } catch {}

      const { x: workX, y: workY, width: workW, height: workH } = targetDisplay.workArea
      const width = 390
      const height = 120
      const x = Math.round(workX + workW - width - 20)
      const y = Math.round(workY + workH - height - 20)

      if (!this.overlayWindow || this.overlayWindow.isDestroyed()) {
        this.overlayWindow = new BrowserWindow({
          width,
          height,
          x,
          y,
          frame: false,
          transparent: true,
          alwaysOnTop: true,
          focusable: false, // Never steal focus from games or active applications
          skipTaskbar: true, // Do not pollute taskbar or Alt+Tab
          resizable: false,
          hasShadow: false,
          show: false,
          webPreferences: {
            nodeIntegration: false,
            contextIsolation: true
          }
        })

        // Listen for actions via console-message for rock-solid communication without CSP/scheme issues
        this.overlayWindow.webContents.on('console-message', (_event, _level, message) => {
          if (message === 'pullman:click') {
            if (this.onClickCallback) {
              this.onClickCallback()
            }
            this.closeOverlay()
          } else if (message === 'pullman:dismiss') {
            this.closeOverlay()
          } else if (message === 'pullman:pause') {
            if (this.dismissTimer) {
              clearTimeout(this.dismissTimer)
              this.dismissTimer = null
            }
          } else if (message === 'pullman:resume') {
            if (!this.dismissTimer) {
              this.dismissTimer = setTimeout(() => {
                this.closeOverlay()
              }, 4000)
            }
          }
        })

        this.overlayWindow.webContents.on('will-navigate', (event, url) => {
          event.preventDefault()
          if (url.startsWith('pullman-notif://click')) {
            if (this.onClickCallback) {
              this.onClickCallback()
            }
            this.closeOverlay()
          } else if (url.startsWith('pullman-notif://dismiss')) {
            this.closeOverlay()
          }
        })

        this.overlayWindow.on('closed', () => {
          this.overlayWindow = null
        })
      } else {
        this.overlayWindow.setBounds({ x, y, width, height })
      }

      // Level 'screen-saver' ensures rendering on top of fullscreen DirectX/OpenGL games and full-screen windows
      this.overlayWindow.setAlwaysOnTop(true, 'screen-saver')
      this.overlayWindow.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true })

      const html = this.buildHtml(payload)
      this.overlayWindow.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(html)}`)

      // Show without taking focus away from active game or app
      this.overlayWindow.showInactive()

      // Auto dismiss after 7 seconds
      this.dismissTimer = setTimeout(() => {
        this.closeOverlay()
      }, 7000)
    } catch (err) {
      console.warn('[OverlayNotificationService] Failed to show overlay window:', err)
    }
  }

  public closeOverlay(): void {
    if (this.dismissTimer) {
      clearTimeout(this.dismissTimer)
      this.dismissTimer = null
    }
    if (this.overlayWindow && !this.overlayWindow.isDestroyed()) {
      try {
        this.overlayWindow.close()
      } catch {}
      this.overlayWindow = null
    }
  }

  private escapeHtml(str: string): string {
    return (str || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;')
  }

  private buildHtml(payload: OverlayNotificationPayload): string {
    const rawTitle = payload.title || 'Pullman Notification'
    const escapedTitle = this.escapeHtml(rawTitle)
    const escapedBody = this.escapeHtml(payload.body || '')
    const actionLabel = payload.issueId !== undefined ? 'Buka Tiket ↗' : 'Buka Pullman ↗'

    return `<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; user-select: none; }
  body {
    background: transparent;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
    overflow: hidden;
    height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 6px;
  }
  .card {
    width: 100%;
    background: rgba(20, 24, 33, 0.96);
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    border: 1px solid #334155;
    border-radius: 12px;
    box-shadow: 0 12px 36px rgba(0, 0, 0, 0.85), 0 4px 12px rgba(0, 0, 0, 0.6);
    padding: 10px 14px;
    display: flex;
    flex-direction: column;
    gap: 5px;
    cursor: pointer;
    position: relative;
    overflow: hidden;
    animation: slideIn 0.28s cubic-bezier(0.16, 1, 0.3, 1) forwards;
  }
  @keyframes slideIn {
    from { transform: translateY(18px) scale(0.97); opacity: 0; }
    to { transform: translateY(0) scale(1); opacity: 1; }
  }
  .card:hover {
    border-color: #3b82f6;
    background: rgba(28, 33, 44, 0.98);
  }
  .header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
  }
  .title-area {
    display: flex;
    align-items: center;
    gap: 7px;
    min-width: 0;
    flex: 1;
  }
  .dot {
    width: 8px;
    height: 8px;
    background: #10b981;
    border-radius: 50%;
    box-shadow: 0 0 8px #10b981;
    flex-shrink: 0;
  }
  .app-name {
    font-size: 11.5px;
    font-weight: 700;
    color: #60a5fa;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .close-btn {
    width: 22px;
    height: 22px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 6px;
    color: #94a3b8;
    background: transparent;
    border: none;
    cursor: pointer;
    font-size: 13px;
    line-height: 1;
    transition: background 0.15s, color 0.15s;
    flex-shrink: 0;
  }
  .close-btn:hover {
    background: rgba(255, 255, 255, 0.12);
    color: #ffffff;
  }
  .body-text {
    font-size: 11.5px;
    color: #e2e8f0;
    line-height: 1.4;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
  .action-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-size: 10px;
    color: #64748b;
    margin-top: 3px;
  }
  .action-hint {
    color: #94a3b8;
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 10px;
  }
  .open-pill {
    background: #2563eb;
    color: white;
    padding: 3px 9px;
    border-radius: 6px;
    font-weight: 600;
    font-size: 10.5px;
    transition: background 0.15s;
  }
  .card:hover .open-pill {
    background: #3b82f6;
  }
  .progress {
    position: absolute;
    bottom: 0;
    left: 0;
    height: 2px;
    background: #3b82f6;
    width: 100%;
    transform-origin: left;
    animation: shrink 7s linear forwards;
  }
  @keyframes shrink {
    from { transform: scaleX(1); }
    to { transform: scaleX(0); }
  }
  .card:hover .progress {
    animation-play-state: paused;
  }
</style>
</head>
<body>
  <div
    class="card"
    onclick="console.log('pullman:click')"
    onmouseenter="console.log('pullman:pause')"
    onmouseleave="console.log('pullman:resume')"
  >
    <div class="header">
      <div class="title-area">
        <div class="dot"></div>
        <span class="app-name">${escapedTitle}</span>
      </div>
      <button
        class="close-btn"
        onclick="event.stopPropagation(); console.log('pullman:dismiss')"
        title="Tutup"
      >✕</button>
    </div>
    <div class="body-text">${escapedBody}</div>
    <div class="action-bar">
      <span class="action-hint">Pullman Desktop</span>
      <span class="open-pill">${actionLabel}</span>
    </div>
    <div class="progress"></div>
  </div>
</body>
</html>`
  }
}

export const overlayNotificationService = new OverlayNotificationService()

