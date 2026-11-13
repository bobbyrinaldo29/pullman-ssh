import { app, BrowserWindow, Notification, nativeImage } from 'electron'
import { join } from 'path'
import { existsSync } from 'fs'
import { execFile } from 'child_process'
import notifier from 'node-notifier'

export interface NotificationPayload {
  title: string
  subtitle?: string
  body: string
  silent?: boolean
  tag?: string
  issueId?: number
}

class NotificationService {
  private iconPath: string | null = null

  private getIconPath(assetPath?: string): string | undefined {
    if (this.iconPath && existsSync(this.iconPath)) {
      return this.iconPath
    }

    const possiblePaths = [
      assetPath,
      join(__dirname, '../../resources/icon.png'),
      join(app.getAppPath(), 'resources/icon.png'),
      join(process.resourcesPath || '', 'icon.png')
    ].filter(Boolean) as string[]

    for (const p of possiblePaths) {
      if (existsSync(p)) {
        this.iconPath = p
        return p
      }
    }
    return undefined
  }

  private showMacNotificationDirect(title: string, body: string, subtitle?: string, sound: boolean = true): void {
    try {
      const cleanTitle = (title || 'Pullman').replace(/\r?\n/g, ' ').replace(/["\\]/g, ' ').trim()
      const cleanBody = (body || '').replace(/\r?\n/g, ' ').replace(/["\\]/g, ' ').trim()
      const cleanSubtitle = (subtitle || '').replace(/\r?\n/g, ' ').replace(/["\\]/g, ' ').trim()

      let script = `display notification "${cleanBody}" with title "${cleanTitle}"`
      if (cleanSubtitle) {
        script += ` subtitle "${cleanSubtitle}"`
      }
      if (sound) {
        script += ` sound name "default"`
      }

      execFile('osascript', ['-e', script], (err) => {
        if (err) {
          console.warn('[NotificationService] osascript warning:', err.message)
        }
      })
    } catch (e) {
      console.warn('[NotificationService] osascript execution error:', e)
    }
  }

  public show(event: Electron.IpcMainInvokeEvent, payload: NotificationPayload, assetIcon?: string): boolean {
    try {
      const { title, subtitle, body, silent, tag, issueId } = payload

      // Visual dock bounce feedback on macOS
      if (process.platform === 'darwin') {
        try {
          app.dock?.bounce?.('informational')
        } catch {}
      }

      const onNotificationClicked = (): void => {
        try {
          const win = BrowserWindow.fromWebContents(event.sender) || BrowserWindow.getAllWindows()[0]
          if (win && !win.isDestroyed()) {
            if (process.platform === 'darwin') {
              app.dock?.show()
              app.focus({ steal: true })
            }

            if (win.isMinimized()) {
              win.restore()
            }

            if (process.platform === 'win32') {
              win.setAlwaysOnTop(true)
              win.show()
              win.focus()
              win.setAlwaysOnTop(false)
            } else {
              win.show()
              win.focus()
            }

            if (tag || issueId !== undefined) {
              win.webContents.send('app:notification-clicked', { tag, issueId })
            }
          }
        } catch (clickErr) {
          console.error('[NotificationService] Click handler error:', clickErr)
        }
      }

      // macOS platform handling
      if (process.platform === 'darwin') {
        this.showMacNotificationDirect(title, body, subtitle, !silent)

        // Also register with Electron Notification if supported
        try {
          if (Notification.isSupported()) {
            const notif = new Notification({
              title: title || 'Pullman',
              subtitle: subtitle || undefined,
              body: body || '',
              silent: Boolean(silent)
            })
            notif.on('click', onNotificationClicked)
            notif.show()
          }
        } catch {}

        return true
      }

      // Windows and Linux handling
      const icon = this.getIconPath(assetIcon)

      try {
        notifier.notify(
          {
            title: title || 'Pullman',
            subtitle: subtitle || undefined,
            message: body || '',
            icon: icon,
            sound: !silent,
            wait: true
          },
          (err) => {
            if (err) {
              console.warn('[NotificationService] node-notifier error:', err)
            }
          }
        )

        notifier.once('click', () => {
          onNotificationClicked()
        })
      } catch (notifierErr) {
        console.warn('[NotificationService] node-notifier warning:', notifierErr)
      }

      // Also trigger Electron Notification for Windows/Linux
      try {
        if (Notification.isSupported()) {
          const electronOptions: Electron.NotificationConstructorOptions = {
            title: title || 'Pullman',
            body: body || '',
            silent: Boolean(silent)
          }
          if (icon) {
            const nativeImg = nativeImage.createFromPath(icon)
            if (!nativeImg.isEmpty()) {
              electronOptions.icon = nativeImg
            }
          }
          if (process.platform === 'linux') {
            electronOptions.urgency = 'normal'
          }
          const notif = new Notification(electronOptions)
          notif.on('click', onNotificationClicked)
          notif.show()
        }
      } catch {}

      return true
    } catch (err) {
      console.error('[NotificationService] Error showing notification:', err)
      return false
    }
  }
}

export const notificationService = new NotificationService()
