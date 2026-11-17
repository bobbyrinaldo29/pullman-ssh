import type { Terminal } from '@xterm/xterm'
import type { Ref } from 'vue'

export function setupTerminalKeyHandler(
  term: Terminal,
  tabId: string,
  asSudo: Ref<boolean>
): void {
  const isMac =
    typeof navigator !== 'undefined' &&
    (/Mac|iPod|iPhone|iPad/.test(navigator.platform || '') || /Mac/.test(navigator.userAgent || ''))

  term.attachCustomKeyEventHandler((e: KeyboardEvent) => {
    if (e.type !== 'keydown') return true

    const isC = e.code === 'KeyC' || e.key === 'c' || e.key === 'C' || e.keyCode === 67
    const isV = e.code === 'KeyV' || e.key === 'v' || e.key === 'V' || e.keyCode === 86

    // =========================================================================
    // 1. CONTROL + C / COMMAND + C (Interrupt SIGINT & Copy)
    // =========================================================================
    if (isC) {
      // Physical Control + C (Mac, Windows, and Linux)
      if (e.ctrlKey && !e.altKey) {
        // Windows/Linux copy if text selected (without Shift)
        if (!isMac && term.hasSelection() && !e.shiftKey) {
          try {
            navigator.clipboard?.writeText(term.getSelection())
            term.clearSelection()
          } catch {}
          e.preventDefault()
          e.stopPropagation()
          return false
        }

        // Send SIGINT (\x03) on Mac, or Windows/Linux without selection (or Ctrl+Shift+C)
        e.preventDefault()
        e.stopPropagation()
        if (asSudo.value) asSudo.value = false
        if (term.hasSelection()) term.clearSelection()
        if (window.api?.sshShellWrite) {
          window.api.sshShellWrite(tabId, '\x03')
        }
        return false
      }

      // Command + C on macOS (metaKey)
      if (isMac && e.metaKey && !e.ctrlKey && !e.altKey) {
        if (term.hasSelection()) {
          try {
            navigator.clipboard?.writeText(term.getSelection())
          } catch {}
          e.preventDefault()
          e.stopPropagation()
          return false
        } else {
          // If no selection on macOS, treat Cmd+C as interrupt
          e.preventDefault()
          e.stopPropagation()
          if (asSudo.value) asSudo.value = false
          if (window.api?.sshShellWrite) {
            window.api.sshShellWrite(tabId, '\x03')
          }
          return false
        }
      }
    }

    // =========================================================================
    // 2. PASTE HANDLING (Cmd+V on Mac, Ctrl+V / Ctrl+Shift+V on Win/Linux)
    // =========================================================================
    if (isV && !e.altKey) {
      const isPaste = isMac
        ? (e.metaKey && !e.ctrlKey)
        : ((e.ctrlKey && e.shiftKey) || (e.ctrlKey && !e.metaKey))

      if (isPaste) {
        e.preventDefault()
        e.stopPropagation()
        navigator.clipboard?.readText().then((text) => {
          if (text && window.api?.sshShellWrite) {
            window.api.sshShellWrite(tabId, text)
          }
        }).catch(() => {})
        return false
      }
    }

    // =========================================================================
    // 3. COMMON CONTROL SHORTCUTS ON MAC (Ctrl+D EOF, Ctrl+Z SIGTSTP, Ctrl+L Clear)
    // =========================================================================
    if (isMac && e.ctrlKey && !e.metaKey && !e.altKey) {
      if (e.code === 'KeyD' || e.key === 'd' || e.key === 'D') {
        e.preventDefault(); e.stopPropagation()
        if (window.api?.sshShellWrite) window.api.sshShellWrite(tabId, '\x04')
        return false
      }
      if (e.code === 'KeyZ' || e.key === 'z' || e.key === 'Z') {
        e.preventDefault(); e.stopPropagation()
        if (window.api?.sshShellWrite) window.api.sshShellWrite(tabId, '\x1a')
        return false
      }
      if (e.code === 'KeyL' || e.key === 'l' || e.key === 'L') {
        e.preventDefault(); e.stopPropagation()
        if (window.api?.sshShellWrite) window.api.sshShellWrite(tabId, '\x0c')
        return false
      }
    }

    return true
  })
}

export function handleTerminalContextMenu(term: Terminal | null, tabId: string, e: MouseEvent): void {
  if (term?.hasSelection()) {
    try {
      navigator.clipboard?.writeText(term.getSelection())
    } catch {}
    return
  }
  e.preventDefault()
  navigator.clipboard?.readText().then((text) => {
    if (text && window.api?.sshShellWrite) {
      window.api.sshShellWrite(tabId, text)
    }
  }).catch(() => {})
}

