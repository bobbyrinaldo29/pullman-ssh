<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { Code } from 'lucide-vue-next'
import { EditorTab, EditorCursorPos, GitBlameInfo } from '../types'
import { monaco, getMonacoLanguage } from '../monaco/monacoSetup'
import { getEnclosingSymbolsAtPosition, getDocumentOutlineSymbols, BreadcrumbSymbol, DocumentOutlineSymbol } from '../services/treeSitterService'
import EditorBreadcrumbBar from './EditorBreadcrumbBar.vue'
import EditorSymbolOutlineModal from './EditorSymbolOutlineModal.vue'
import '../monaco/editorMonaco.css'

const props = defineProps<{
  activeTab: EditorTab | null
  cursorPos?: EditorCursorPos
  blame?: GitBlameInfo | null
  hostName?: string
}>()

const emit = defineEmits<{
  (e: 'cursor-change', pos: EditorCursorPos): void
  (e: 'diagnostics-change', errors: string[]): void
  (e: 'save'): void
  (e: 'save-as-sudo'): void
  (e: 'toggle-ai-gen'): void
  (e: 'open-git-graph'): void
}>()

const containerRef = ref<HTMLDivElement | null>(null)
let editor: monaco.editor.IStandaloneCodeEditor | null = null
let resizeObserver: ResizeObserver | null = null

const activeSymbols = ref<BreadcrumbSymbol[]>([])
const outlineSymbols = ref<DocumentOutlineSymbol[]>([])
const isOutlineModalOpen = ref(false)

async function updateOutlineSymbols(): Promise<void> {
  if (!editor || !props.activeTab) {
    outlineSymbols.value = []
    return
  }
  const model = editor.getModel()
  if (!model) return
  const lang = getMonacoLanguage(props.activeTab.name || props.activeTab.path)
  try {
    const syms = await getDocumentOutlineSymbols(model, lang)
    outlineSymbols.value = syms
  } catch {
    outlineSymbols.value = []
  }
}

async function updateActiveSymbols(line: number, col: number): Promise<void> {
  if (!editor || !props.activeTab) {
    activeSymbols.value = []
    return
  }
  const model = editor.getModel()
  if (!model) return
  const lang = getMonacoLanguage(props.activeTab.name || props.activeTab.path)
  try {
    const syms = await getEnclosingSymbolsAtPosition(model, lang, line, col)
    activeSymbols.value = syms
  } catch {
    activeSymbols.value = []
  }
}

// Cache models per tab to preserve undo/redo history and cursor states
const modelMap = new Map<string, monaco.editor.ITextModel>()

// Git Blame Content Widget DOM Node
const blameWidgetNode = document.createElement('div')
blameWidgetNode.className = 'monaco-git-blame-inline'
blameWidgetNode.style.display = 'none'

function escapeHtml(str: string): string {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

function updateBlameContentWidget(): void {
  if (!editor) return

  const blame = props.blame
  if (!blame || !blame.author) {
    blameWidgetNode.style.display = 'none'
    blameWidgetNode.innerHTML = ''
    editor.layoutContentWidget(gitBlameContentWidget)
    return
  }

  const pos = editor.getPosition()
  const model = editor.getModel()
  if (!pos || !model) {
    blameWidgetNode.style.display = 'none'
    editor.layoutContentWidget(gitBlameContentWidget)
    return
  }

  const lineContent = model.getLineContent(pos.lineNumber)
  if (!lineContent.trim()) {
    blameWidgetNode.style.display = 'none'
    editor.layoutContentWidget(gitBlameContentWidget)
    return
  }

  const isCleanCommit = Boolean(blame.hash && !blame.isUncommitted && !blame.hash.startsWith('0000000') && blame.hash !== 'dirty')
  const displayHash = isCleanCommit ? (blame.hash || '').substring(0, 7) : 'Uncommitted'

  blameWidgetNode.style.display = 'inline-flex'
  blameWidgetNode.innerHTML = `<div class="git-blame-badge" title="GitLens Blame: ${escapeHtml(blame.author)}, ${escapeHtml(blame.timeAgo || '')}"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="git-blame-icon"><circle cx="12" cy="12" r="3"></circle><line x1="3" y1="12" x2="9" y2="12"></line><line x1="15" y1="12" x2="21" y2="12"></line></svg><span class="git-blame-author">${escapeHtml(blame.author)}</span><span class="git-blame-time">${escapeHtml(blame.timeAgo || '')}</span><span class="git-blame-sep">•</span><span class="git-blame-summary">${escapeHtml(blame.summary || '')}</span></div><div class="git-blame-popover"><div class="git-blame-popover-header"><div class="git-blame-popover-hash"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:12px;height:12px;color:#38bdf8;"><circle cx="12" cy="12" r="3"></circle><line x1="3" y1="12" x2="9" y2="12"></line><line x1="15" y1="12" x2="21" y2="12"></line></svg><span>${displayHash}</span></div><div class="git-blame-popover-actions">${isCleanCommit ? `<button type="button" class="git-blame-action-btn" data-blame-action="copy">Copy SHA</button>` : ''}<button type="button" class="git-blame-action-btn git-blame-action-graph" data-blame-action="graph">Git Graph</button></div></div><div class="git-blame-popover-body"><div class="git-blame-popover-author"><strong>${escapeHtml(blame.author)}</strong> <span style="color:#64748b;">committed ${escapeHtml(blame.timeAgo || '')}</span></div><div class="git-blame-popover-msg">${escapeHtml(blame.summary || '')}</div></div></div>`

  editor.layoutContentWidget(gitBlameContentWidget)
}

const gitBlameContentWidget: monaco.editor.IContentWidget = {
  getId: () => 'pullman.editor.gitBlameWidget',
  getDomNode: () => blameWidgetNode,
  getPosition: () => {
    if (!props.blame || !props.blame.author || !editor) return null
    const pos = editor.getPosition()
    const model = editor.getModel()
    if (!pos || !model) return null

    const lineContent = model.getLineContent(pos.lineNumber)
    if (!lineContent.trim()) return null

    const maxCol = model.getLineMaxColumn(pos.lineNumber)
    return {
      position: { lineNumber: pos.lineNumber, column: maxCol },
      preference: [monaco.editor.ContentWidgetPositionPreference.EXACT]
    }
  }
}

function getOrCreateModel(tab: EditorTab): monaco.editor.ITextModel {
  const existing = modelMap.get(tab.id)
  if (existing && !existing.isDisposed()) {
    if (existing.getValue() !== tab.content && !tab.isDirty) {
      existing.setValue(tab.content)
    }
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

function initMonaco(): void {
  if (!containerRef.value || editor) return

  try {
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
      fixedOverflowWidgets: true,
      formatOnPaste: true
    })
  } catch (err) {
    console.warn('Failed to create Monaco editor with pullman-dark theme, falling back to vs-dark:', err)
    editor = monaco.editor.create(containerRef.value, {
      theme: 'vs-dark',
      automaticLayout: true,
      fontSize: 13,
      fontFamily: "'Fira Code', Menlo, Monaco, 'Courier New', monospace",
      lineHeight: 22,
      tabSize: 2,
      minimap: { enabled: true, maxColumn: 80, scale: 1 },
      scrollBeyondLastLine: false,
      renderLineHighlight: 'all'
    })
  }

  // Add Git Blame content widget
  editor.addContentWidget(gitBlameContentWidget)

  // Track cursor position
  editor.onDidChangeCursorPosition((e) => {
    emit('cursor-change', { line: e.position.lineNumber, col: e.position.column })
    updateBlameContentWidget()
    updateActiveSymbols(e.position.lineNumber, e.position.column)
  })

  // Track scroll position to keep blame widget aligned
  editor.onDidScrollChange(() => {
    updateBlameContentWidget()
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

  // Quick Outline Modal shortcut: Cmd+Shift+O / Ctrl+Shift+O
  editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyMod.Shift | monaco.KeyCode.KeyO, () => {
    isOutlineModalOpen.value = true
  })

  // Set model if active tab exists
  if (props.activeTab) {
    const model = getOrCreateModel(props.activeTab)
    editor.setModel(model)
    updateBlameContentWidget()
    updateOutlineSymbols()
  }

  // Trigger immediate layout
  nextTick(() => {
    editor?.layout()
  })

  // Setup ResizeObserver for layout
  resizeObserver = new ResizeObserver(() => {
    editor?.layout()
    updateBlameContentWidget()
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
    updateBlameContentWidget()
    updateOutlineSymbols()
    nextTick(() => {
      editor?.layout()
    })
    const pos = editor.getPosition()
    if (pos) updateActiveSymbols(pos.lineNumber, pos.column)
  } else {
    activeSymbols.value = []
    outlineSymbols.value = []
    editor.setModel(null)
    updateBlameContentWidget()
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
  () => props.activeTab?.content,
  (newContent) => {
    if (!editor || !props.activeTab || newContent === undefined) return
    const model = editor.getModel()
    if (model && model.getValue() !== newContent && !props.activeTab.isDirty) {
      model.setValue(newContent)
    }
  }
)

watch(
  () => props.blame,
  () => {
    updateBlameContentWidget()
  },
  { deep: true }
)

// Public Methods
function goToLine(lineNumber: number): void {
  if (!editor || lineNumber <= 0) return
  editor.revealLineInCenter(lineNumber)
  editor.setPosition({ lineNumber, column: 1 })
  editor.focus()
  updateBlameContentWidget()
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
  blameWidgetNode.onclick = (e: MouseEvent) => {
    e.stopPropagation()
    const target = e.target as HTMLElement
    const copyBtn = target.closest('[data-blame-action="copy"]') as HTMLElement | null
    const graphBtn = target.closest('[data-blame-action="graph"]') as HTMLElement | null
    if (copyBtn && props.blame?.hash) {
      navigator.clipboard.writeText(props.blame.hash)
      const oldText = copyBtn.innerText
      copyBtn.innerText = '✓ Copied'
      setTimeout(() => {
        if (copyBtn) copyBtn.innerText = oldText
      }, 1500)
    } else if (graphBtn) {
      emit('open-git-graph')
    }
  }

  nextTick(() => {
    if (props.activeTab && containerRef.value) {
      initMonaco()
    }
  })
})

onUnmounted(() => {
  resizeObserver?.disconnect()
  try {
    editor?.removeContentWidget(gitBlameContentWidget)
  } catch {}
  for (const m of modelMap.values()) {
    if (!m.isDisposed()) m.dispose()
  }
  modelMap.clear()
  editor?.dispose()
  editor = null
})
</script>

<template>
  <div class="flex-1 flex flex-col bg-[#1E222B] relative z-10 min-h-0">
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

    <!-- Tree-sitter AST & Path Breadcrumb Bar -->
    <EditorBreadcrumbBar
      v-if="activeTab && activeTab.viewType !== 'diff'"
      :file-path="activeTab.path"
      :file-name="activeTab.name"
      :symbols="activeSymbols"
      :host-name="hostName"
      @select-symbol="(sym) => goToLine(sym.range.startLineNumber)"
      @open-outline="isOutlineModalOpen = true"
    />

    <!-- Quick Outline Modal -->
    <EditorSymbolOutlineModal
      :is-open="isOutlineModalOpen"
      :symbols="outlineSymbols"
      :file-name="activeTab?.name"
      :active-symbol-name="activeSymbols.length > 0 ? activeSymbols[activeSymbols.length - 1].name : undefined"
      @select="(line) => goToLine(line)"
      @close="isOutlineModalOpen = false"
    />

    <!-- Monaco Code Editor Host Element -->
    <div
      v-show="activeTab"
      ref="containerRef"
      class="flex-1 w-full min-h-0 bg-[#1E222B] text-[#abb2bf] overflow-hidden"
    ></div>
  </div>
</template>

<style scoped>
/* Scoped styles kept minimal; Monaco and GitLens styles are maintained in ../monaco/editorMonaco.css */
</style>
