<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { Code } from 'lucide-vue-next'
import { EditorTab, EditorCursorPos, GitBlameInfo } from '../types'
import { monaco, getMonacoLanguage } from '../monaco/monacoSetup'

const props = defineProps<{
  activeTab: EditorTab | null
  cursorPos?: EditorCursorPos
  blame?: GitBlameInfo | null
}>()

const emit = defineEmits<{
  (e: 'cursor-change', pos: EditorCursorPos): void
  (e: 'diagnostics-change', errors: string[]): void
  (e: 'save'): void
  (e: 'save-as-sudo'): void
  (e: 'toggle-ai-gen'): void
}>()

const containerRef = ref<HTMLDivElement | null>(null)
let editor: monaco.editor.IStandaloneCodeEditor | null = null
let resizeObserver: ResizeObserver | null = null

// Cache models per tab to preserve undo/redo history and cursor states
const modelMap = new Map<string, monaco.editor.ITextModel>()
let blameDecorations: string[] = []

function getOrCreateModel(tab: EditorTab): monaco.editor.ITextModel {
  const existing = modelMap.get(tab.id)
  if (existing && !existing.isDisposed()) {
    return existing
  }

  const lang = getMonacoLanguage(tab.name || tab.path || tab.language)
  const uri = monaco.Uri.parse(`inmemory://pullman/${tab.id}/${encodeURIComponent(tab.name || 'untitled')}`)
  const model = monaco.editor.createModel(tab.content, lang, uri)

  model.onDidChangeContent(() => {
    if (props.activeTab && props.activeTab.id === tab.id) {
      props.activeTab.content = model.getValue()
      props.activeTab.isDirty = props.activeTab.content !== props.activeTab.originalContent
    }
  })

  modelMap.set(tab.id, model)
  return model
}

function updateBlameGhost(): void {
  if (!editor) return
  if (!props.blame || !props.blame.hash || !props.blame.author) {
    blameDecorations = editor.deltaDecorations(blameDecorations, [])
    return
  }

  const pos = editor.getPosition()
  if (!pos) return
  const line = pos.lineNumber
  const model = editor.getModel()
  if (!model) return

  const lineContent = model.getLineContent(line)
  if (!lineContent.trim()) {
    blameDecorations = editor.deltaDecorations(blameDecorations, [])
    return
  }

  const maxCol = model.getLineMaxColumn(line)
  blameDecorations = editor.deltaDecorations(blameDecorations, [
    {
      range: new monaco.Range(line, maxCol, line, maxCol),
      options: {
        after: {
          content: `   ${props.blame.author} • ${props.blame.timeAgo} • ${props.blame.summary}`,
          inlineClassName: 'monaco-blame-ghost'
        }
      }
    }
  ])
}

function initMonaco(): void {
  if (!containerRef.value || editor) return

  editor = monaco.editor.create(containerRef.value, {
    theme: 'pullman-dark',
    automaticLayout: true,
    fontSize: 13,
    fontFamily: "'Fira Code', Menlo, Monaco, 'Courier New', monospace",
    lineHeight: 22,
    tabSize: 2,
    minimap: { enabled: true, maxColumn: 80, scale: 1 },
    scrollBeyondLastLine: false,
    renderLineHighlight: 'all',
    cursorBlinking: 'smooth',
    cursorSmoothCaretAnimation: 'on',
    smoothScrolling: true,
    bracketPairColorization: { enabled: true },
    guides: { indentation: true, bracketPairs: true },
    padding: { top: 10, bottom: 10 },
    roundedSelection: true,
    formatOnPaste: true
  })

  // Track cursor position
  editor.onDidChangeCursorPosition((e) => {
    emit('cursor-change', { line: e.position.lineNumber, col: e.position.column })
    updateBlameGhost()
  })

  // Keyboard Shortcuts: Save, Save as Sudo, AI Gen, Wrap Log
  editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, () => {
    emit('save')
  })

  editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyMod.Alt | monaco.KeyCode.KeyS, () => {
    emit('save-as-sudo')
  })

  editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyK, () => {
    emit('toggle-ai-gen')
  })

  editor.addCommand(monaco.KeyMod.Alt | monaco.KeyCode.KeyL, () => {
    handleWrapLog()
  })

  // Set model if active tab exists
  if (props.activeTab) {
    const model = getOrCreateModel(props.activeTab)
    editor.setModel(model)
  }

  // Setup ResizeObserver for layout
  resizeObserver = new ResizeObserver(() => {
    editor?.layout()
  })
  resizeObserver.observe(containerRef.value)
}

function switchTabModel(): void {
  if (!editor) return

  if (props.activeTab) {
    const model = getOrCreateModel(props.activeTab)
    if (editor.getModel() !== model) {
      editor.setModel(model)
    }
    // Update language if changed
    const lang = getMonacoLanguage(props.activeTab.name || props.activeTab.path || props.activeTab.language)
    if (model.getLanguageId() !== lang) {
      monaco.editor.setModelLanguage(model, lang)
    }
    editor.focus()
    updateBlameGhost()
  } else {
    editor.setModel(null)
  }
}

watch(
  () => props.activeTab?.id,
  () => {
    nextTick(() => {
      if (!editor && containerRef.value) {
        initMonaco()
      } else {
        switchTabModel()
      }
    })
  }
)

watch(
  () => props.blame,
  () => {
    updateBlameGhost()
  },
  { deep: true }
)

// Public Methods
function goToLine(lineNumber: number): void {
  if (!editor || lineNumber <= 0) return
  editor.revealLineInCenter(lineNumber)
  editor.setPosition({ lineNumber, column: 1 })
  editor.focus()
}

function insertSnippet(code: string): void {
  if (!editor) return
  const selection = editor.getSelection()
  if (selection) {
    editor.executeEdits('insert-snippet', [
      { range: selection, text: code, forceMoveMarkers: true }
    ])
  } else {
    editor.trigger('keyboard', 'type', { text: code })
  }
  editor.focus()
}

function handleWrapLog(): void {
  if (!editor || !props.activeTab) return
  const selection = editor.getSelection()
  const model = editor.getModel()
  if (!model || !selection) return

  let selectedText = model.getValueInRange(selection).trim()
  if (!selectedText) {
    const word = model.getWordAtPosition(selection.getPosition())
    if (word) {
      selectedText = word.word
    }
  }

  const lang = (props.activeTab.language || '').toLowerCase()
  let statement = ''
  if (lang.includes('php')) {
    statement = selectedText ? `error_log('${selectedText}: ' . print_r(${selectedText}, true));` : `error_log('DEBUG: ' . __FILE__ . ':' . __LINE__);`
  } else if (lang.includes('python') || lang.includes('py')) {
    statement = selectedText ? `print(f"${selectedText}: {${selectedText}}")` : `print("DEBUG:", __file__)`
  } else {
    statement = selectedText ? `console.log('${selectedText}:', ${selectedText});` : `console.log('DEBUG');`
  }

  const line = selection.endLineNumber
  const lineContent = model.getLineContent(line)
  const indent = lineContent.match(/^\s*/)?.[0] || ''
  const insertText = `\n${indent}${statement}`

  const endOfLineCol = model.getLineMaxColumn(line)
  editor.executeEdits('wrap-log', [
    {
      range: new monaco.Range(line, endOfLineCol, line, endOfLineCol),
      text: insertText,
      forceMoveMarkers: true
    }
  ])
  editor.setPosition({ lineNumber: line + 1, column: indent.length + statement.length + 1 })
  editor.focus()
}

defineExpose({
  goToLine,
  handleWrapLog,
  insertSnippet
})

onMounted(() => {
  nextTick(() => {
    if (props.activeTab && containerRef.value) {
      initMonaco()
    }
  })
})

onUnmounted(() => {
  resizeObserver?.disconnect()
  for (const m of modelMap.values()) {
    if (!m.isDisposed()) m.dispose()
  }
  modelMap.clear()
  editor?.dispose()
  editor = null
})
</script>

<template>
  <div class="flex-1 flex flex-col bg-[#1E222B] overflow-hidden relative">
    <!-- Empty Welcome Screen when no file is open -->
    <div
      v-if="!activeTab"
      class="flex-1 flex flex-col items-center justify-center p-8 text-center select-none"
    >
      <div class="w-16 h-16 rounded-3xl bg-[#252A36] border border-[#2F374A] flex items-center justify-center text-blue-400 mb-4 shadow-xl">
        <Code class="w-8 h-8" />
      </div>
      <h2 class="text-base font-semibold text-white">Pullman SSH Code Editor</h2>
      <p class="text-xs text-slate-400 mt-2 max-w-sm leading-relaxed">
        Powered by Monaco Editor. Select or open any remote file from the explorer sidebar to begin editing with full VS Code capabilities.
      </p>
      <div class="mt-6 flex flex-wrap gap-2 justify-center max-w-md text-[11px] text-slate-400">
        <span class="px-2.5 py-1 bg-[#252B3A] border border-[#2E364A] rounded-lg font-mono">⌘S / Ctrl+S Save</span>
        <span class="px-2.5 py-1 bg-[#252B3A] border border-[#2E364A] rounded-lg font-mono">⌘⌥S Save Sudo</span>
        <span class="px-2.5 py-1 bg-[#252B3A] border border-[#2E364A] rounded-lg font-mono">⌘K AI Gen</span>
        <span class="px-2.5 py-1 bg-[#252B3A] border border-[#2E364A] rounded-lg font-mono">⌥L Wrap Log</span>
        <span class="px-2.5 py-1 bg-[#252B3A] border border-[#2E364A] rounded-lg font-mono">⌘\ Split View</span>
      </div>
    </div>

    <!-- Monaco Code Editor Host Element -->
    <div
      v-show="activeTab"
      ref="containerRef"
      class="flex-1 w-full h-full overflow-hidden"
    ></div>
  </div>
</template>

<style scoped>
:deep(.monaco-blame-ghost) {
  color: #5c6370 !important;
  font-style: italic !important;
  font-size: 11px !important;
  opacity: 0.6 !important;
  pointer-events: none !important;
}
</style>
