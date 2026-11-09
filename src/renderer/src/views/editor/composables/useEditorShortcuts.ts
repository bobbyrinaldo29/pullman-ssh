import { nextTick } from 'vue'
import { EditorTab } from '../types'
import { useEditorHistory } from './useEditorHistory'
import {
  moveLine,
  duplicateLine,
  deleteLine,
  toggleLineComment,
  CommandResult
} from '../utils/editorCommands'

export function useEditorShortcuts() {
  const { reset: resetHistory, recordState, undo, redo } = useEditorHistory()

  function applyResult(
    res: CommandResult | null,
    textarea: HTMLTextAreaElement,
    tab: EditorTab,
    onAfterUpdate?: () => void
  ): boolean {
    if (!res) return false

    tab.content = res.newContent
    tab.isDirty = tab.content !== tab.originalContent
    recordState(res.newContent, res.newEnd, true)

    nextTick(() => {
      textarea.selectionStart = res.newStart
      textarea.selectionEnd = res.newEnd
      textarea.focus()
      onAfterUpdate?.()
    })
    return true
  }

  function handleUndo(
    textarea: HTMLTextAreaElement,
    tab: EditorTab,
    onAfterUpdate?: () => void
  ): boolean {
    const target = undo(tab.content, textarea.selectionStart)
    if (!target) return false

    tab.content = target.content
    tab.isDirty = tab.content !== tab.originalContent

    nextTick(() => {
      textarea.selectionStart = textarea.selectionEnd = target.cursor
      textarea.focus()
      onAfterUpdate?.()
    })
    return true
  }

  function handleRedo(
    textarea: HTMLTextAreaElement,
    tab: EditorTab,
    onAfterUpdate?: () => void
  ): boolean {
    const target = redo(tab.content, textarea.selectionStart)
    if (!target) return false

    tab.content = target.content
    tab.isDirty = tab.content !== tab.originalContent

    nextTick(() => {
      textarea.selectionStart = textarea.selectionEnd = target.cursor
      textarea.focus()
      onAfterUpdate?.()
    })
    return true
  }

  function processKeyDown(
    e: KeyboardEvent,
    textarea: HTMLTextAreaElement,
    tab: EditorTab,
    onAfterUpdate?: () => void
  ): boolean {
    // 1. Undo: Cmd+Z or Ctrl+Z
    if ((e.metaKey || e.ctrlKey) && !e.shiftKey && (e.key === 'z' || e.key === 'Z')) {
      e.preventDefault()
      return handleUndo(textarea, tab, onAfterUpdate)
    }

    // 2. Redo: Cmd+Shift+Z or Ctrl+Shift+Z or Ctrl+Y
    if (
      ((e.metaKey || e.ctrlKey) && e.shiftKey && (e.key === 'z' || e.key === 'Z')) ||
      (!e.metaKey && e.ctrlKey && (e.key === 'y' || e.key === 'Y'))
    ) {
      e.preventDefault()
      return handleRedo(textarea, tab, onAfterUpdate)
    }

    // 3. Toggle Line Comment: Cmd+/ or Ctrl+/
    if ((e.metaKey || e.ctrlKey) && (e.key === '/' || e.code === 'Slash')) {
      e.preventDefault()
      return applyResult(
        toggleLineComment(tab.content, textarea.selectionStart, textarea.selectionEnd, tab.language),
        textarea,
        tab,
        onAfterUpdate
      )
    }

    // 4. Duplicate Line: Shift+Alt+Down / Shift+Alt+Up (Shift+Option+Down / Up)
    if (e.altKey && e.shiftKey && (e.key === 'ArrowDown' || e.key === 'ArrowUp')) {
      e.preventDefault()
      return applyResult(
        duplicateLine(tab.content, textarea.selectionStart, textarea.selectionEnd, e.key === 'ArrowDown' ? 'down' : 'up'),
        textarea,
        tab,
        onAfterUpdate
      )
    }

    // 5. Move Line: Alt+Down / Alt+Up (Option+Down / Option+Up)
    if (e.altKey && !e.shiftKey && (e.key === 'ArrowDown' || e.key === 'ArrowUp')) {
      e.preventDefault()
      return applyResult(
        moveLine(tab.content, textarea.selectionStart, textarea.selectionEnd, e.key === 'ArrowDown' ? 'down' : 'up'),
        textarea,
        tab,
        onAfterUpdate
      )
    }

    // 6. Delete Line: Cmd+Shift+K or Ctrl+Shift+K
    if ((e.metaKey || e.ctrlKey) && e.shiftKey && (e.key === 'k' || e.key === 'K')) {
      e.preventDefault()
      return applyResult(
        deleteLine(tab.content, textarea.selectionStart, textarea.selectionEnd),
        textarea,
        tab,
        onAfterUpdate
      )
    }

    return false
  }

  return {
    resetHistory,
    recordState,
    handleUndo,
    handleRedo,
    processKeyDown
  }
}

