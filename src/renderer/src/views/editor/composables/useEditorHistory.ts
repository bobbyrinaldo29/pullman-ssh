import { ref } from 'vue'

export interface EditorSnapshot {
  content: string
  cursor: number
  timestamp: number
}

export function useEditorHistory() {
  const undoStack = ref<EditorSnapshot[]>([])
  const redoStack = ref<EditorSnapshot[]>([])
  let lastPushTime = 0

  function reset(initialContent = ''): void {
    undoStack.value = [{ content: initialContent, cursor: 0, timestamp: Date.now() }]
    redoStack.value = []
    lastPushTime = Date.now()
  }

  function recordState(content: string, cursor: number, forceImmediate = false): void {
    const now = Date.now()
    const lastItem = undoStack.value[undoStack.value.length - 1]

    if (lastItem && lastItem.content === content) {
      return
    }

    // Group rapid typing within 500ms if not forceImmediate
    if (!forceImmediate && lastItem && now - lastPushTime < 500) {
      // Update cursor and content of top of stack
      lastItem.content = content
      lastItem.cursor = cursor
      lastItem.timestamp = now
      lastPushTime = now
      return
    }

    undoStack.value.push({ content, cursor, timestamp: now })
    if (undoStack.value.length > 100) {
      undoStack.value.shift()
    }
    redoStack.value = []
    lastPushTime = now
  }

  function undo(currentContent: string, currentCursor: number): EditorSnapshot | null {
    if (undoStack.value.length <= 1) return null

    // Push current active state to redoStack
    redoStack.value.push({
      content: currentContent,
      cursor: currentCursor,
      timestamp: Date.now()
    })

    // Pop the current state from undoStack
    undoStack.value.pop()
    const targetState = undoStack.value[undoStack.value.length - 1]
    return targetState ? { ...targetState } : null
  }

  function redo(currentContent: string, currentCursor: number): EditorSnapshot | null {
    if (redoStack.value.length === 0) return null

    // Push current active state to undoStack
    undoStack.value.push({
      content: currentContent,
      cursor: currentCursor,
      timestamp: Date.now()
    })

    const targetState = redoStack.value.pop()
    return targetState ? { ...targetState } : null
  }

  return {
    undoStack,
    redoStack,
    reset,
    recordState,
    undo,
    redo
  }
}

