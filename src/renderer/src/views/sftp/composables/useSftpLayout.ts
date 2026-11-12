import { ref, reactive } from 'vue'

export function useSftpLayout() {
  // Resizable Split Panes State
  const splitRatio = ref(50)
  const isResizingSplit = ref(false)
  const splitContainerRef = ref<HTMLElement | null>(null)

  function startResizeSplit(e: MouseEvent): void {
    e.preventDefault()
    isResizingSplit.value = true
    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'

    const handleMouseMove = (moveEvent: MouseEvent): void => {
      if (!isResizingSplit.value || !splitContainerRef.value) return
      const rect = splitContainerRef.value.getBoundingClientRect()
      const offsetX = moveEvent.clientX - rect.left
      let newRatio = (offsetX / rect.width) * 100
      if (newRatio < 15) newRatio = 15
      if (newRatio > 85) newRatio = 85
      splitRatio.value = Math.round(newRatio * 10) / 10
    }

    const handleMouseUp = (): void => {
      isResizingSplit.value = false
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
      window.removeEventListener('mousemove', handleMouseMove)
      window.removeEventListener('mouseup', handleMouseUp)
    }

    window.addEventListener('mousemove', handleMouseMove)
    window.addEventListener('mouseup', handleMouseUp)
  }

  // Table Column Resizing State
  const localColWidths = reactive({
    name: 240,
    size: 80,
    date: 150
  })

  const remoteColWidths = reactive({
    name: 220,
    size: 80,
    permissions: 140,
    author: 110,
    date: 150
  })

  const resizingCol = ref<{
    pane: 'local' | 'remote'
    key: string
    startX: number
    startWidth: number
  } | null>(null)

  function startResizeCol(pane: 'local' | 'remote', key: string, e: MouseEvent): void {
    e.preventDefault()
    e.stopPropagation()

    const currentWidth =
      pane === 'local'
        ? localColWidths[key as keyof typeof localColWidths]
        : remoteColWidths[key as keyof typeof remoteColWidths]

    resizingCol.value = {
      pane,
      key,
      startX: e.clientX,
      startWidth: currentWidth
    }

    const minWidthMap: Record<string, number> = {
      name: 80,
      size: 50,
      permissions: 60,
      author: 60,
      date: 90
    }
    const minWidth = minWidthMap[key] || 50

    const handleMouseMove = (moveEvent: MouseEvent): void => {
      if (!resizingCol.value) return
      const delta = moveEvent.clientX - resizingCol.value.startX
      const newWidth = Math.max(minWidth, Math.round(resizingCol.value.startWidth + delta))
      if (resizingCol.value.pane === 'local') {
        localColWidths[resizingCol.value.key as keyof typeof localColWidths] = newWidth
      } else {
        remoteColWidths[resizingCol.value.key as keyof typeof remoteColWidths] = newWidth
      }
    }

    const handleMouseUp = (): void => {
      resizingCol.value = null
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
      window.removeEventListener('mousemove', handleMouseMove)
      window.removeEventListener('mouseup', handleMouseUp)
    }

    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'
    window.addEventListener('mousemove', handleMouseMove)
    window.addEventListener('mouseup', handleMouseUp)
  }

  return {
    splitRatio,
    isResizingSplit,
    splitContainerRef,
    startResizeSplit,
    localColWidths,
    remoteColWidths,
    resizingCol,
    startResizeCol
  }
}

