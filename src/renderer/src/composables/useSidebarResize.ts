import { ref, onUnmounted, type Ref } from 'vue'

const DEFAULT_SIDEBAR_WIDTH = 260
const MIN_SIDEBAR_WIDTH = 180
const MAX_SIDEBAR_WIDTH = 700
const STORAGE_KEY = 'pullman_sidebar_width'

export interface UseSidebarResizeReturn {
  sidebarWidth: Ref<number>
  isResizing: Ref<boolean>
  startResizing: (e: MouseEvent) => void
  resetSidebarWidth: () => void
}

/**
 * Manages persisted horizontal drag resizing for the connection sidebar.
 */
export function useSidebarResize(asideRef: Ref<HTMLElement | null>): UseSidebarResizeReturn {
  const sidebarWidth = ref<number>(DEFAULT_SIDEBAR_WIDTH)
  const isResizing = ref(false)

  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved) {
      const parsed = parseInt(saved, 10)
      if (!isNaN(parsed) && parsed >= MIN_SIDEBAR_WIDTH && parsed <= MAX_SIDEBAR_WIDTH) {
        sidebarWidth.value = parsed
      }
    }
  } catch {
    // ignore storage failures
  }

  let activeMoveHandler: ((e: MouseEvent) => void) | null = null
  let activeStopHandler: (() => void) | null = null

  function cleanupListeners(): void {
    if (activeMoveHandler) {
      window.removeEventListener('mousemove', activeMoveHandler)
      activeMoveHandler = null
    }
    if (activeStopHandler) {
      window.removeEventListener('mouseup', activeStopHandler)
      activeStopHandler = null
    }
    document.body.style.cursor = ''
    document.body.style.userSelect = ''
  }

  function startResizing(e: MouseEvent): void {
    e.preventDefault()
    cleanupListeners()
    isResizing.value = true
    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'

    const asideLeft = asideRef.value?.getBoundingClientRect().left ?? 0

    activeMoveHandler = (moveEvent: MouseEvent): void => {
      if (!isResizing.value) return
      const calculatedWidth = moveEvent.clientX - asideLeft
      const newWidth = Math.min(
        Math.max(calculatedWidth, MIN_SIDEBAR_WIDTH),
        Math.min(window.innerWidth * 0.6, MAX_SIDEBAR_WIDTH)
      )
      sidebarWidth.value = Math.round(newWidth)
    }

    activeStopHandler = (): void => {
      isResizing.value = false
      cleanupListeners()
      try {
        localStorage.setItem(STORAGE_KEY, String(sidebarWidth.value))
      } catch {
        // ignore storage failures
      }
    }

    window.addEventListener('mousemove', activeMoveHandler)
    window.addEventListener('mouseup', activeStopHandler)
  }

  function resetSidebarWidth(): void {
    sidebarWidth.value = DEFAULT_SIDEBAR_WIDTH
    try {
      localStorage.setItem(STORAGE_KEY, String(DEFAULT_SIDEBAR_WIDTH))
    } catch {
      // ignore storage failures
    }
  }

  onUnmounted(() => {
    cleanupListeners()
  })

  return {
    sidebarWidth,
    isResizing,
    startResizing,
    resetSidebarWidth
  }
}
