<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { Code } from 'lucide-vue-next'
import { EditorTab, EditorCursorPos, GitBlameInfo } from '../types'
import { monaco, getMonacoLanguage } from '../monaco/monacoSetup'
import { getEnclosingSymbolsAtPosition, getDocumentOutlineSymbols, BreadcrumbSymbol, DocumentOutlineSymbol } from '../services/treeSitterService'
import { createWrapLogStatement } from '../utils/wrapLog'
import { useEditorSettings } from '../../../composables/useEditorSettings'
import { createGitBlameWidget } from '../services/editorBlameWidget'
import EditorBreadcrumbBar from './EditorBreadcrumbBar.vue'
import EditorSymbolOutlineModal from './EditorSymbolOutlineModal.vue'
import '../monaco/editorMonaco.css'

const props = defineProps<{
  activeTab: EditorTab | null
  tabs?: EditorTab[]
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
const editorSettings = useEditorSettings()
const activeSymbols = ref<BreadcrumbSymbol[]>([])
const outlineSymbols = ref<DocumentOutlineSymbol[]>([])
const isOutlineModalOpen = ref(false)

async function updateOutlineSymbols(): Promise<void> {
  const model = editor?.getModel()
  if (!model || !props.activeTab) { outlineSymbols.value = []; return }
  try {
    outlineSymbols.value = await getDocumentOutlineSymbols(model, getMonacoLanguage(props.activeTab.name || props.activeTab.path))
  } catch {
    outlineSymbols.value = []
  }
}

async function updateActiveSymbols(line: number, col: number): Promise<void> {
  const model = editor?.getModel()
  if (!model || !props.activeTab) { activeSymbols.value = []; return }
  try {
    activeSymbols.value = await getEnclosingSymbolsAtPosition(model, getMonacoLanguage(props.activeTab.name || props.activeTab.path), line, col)
  } catch {
    activeSymbols.value = []
  }
}

// Cache models, tab records & view states (scroll, cursor, selections) per tab
interface TabModelRecord {
  tab: EditorTab
  model: monaco.editor.ITextModel
  changeDebounce: ReturnType<typeof setTimeout> | null
}

const tabRecordMap = new Map<string, TabModelRecord>()
const viewStateMap = new Map<string, monaco.editor.ICodeEditorViewState>()
let currentTabId: string | null = null
let isSwitchingTab = false

const blameWidget = createGitBlameWidget(
  () => editor,
  () => props.blame
)

function flushTabRecord(tabId: string): void {
  const record = tabRecordMap.get(tabId)
  if (!record || record.model.isDisposed()) return
  if (record.changeDebounce) {
    clearTimeout(record.changeDebounce)
    record.changeDebounce = null
  }
  const val = record.model.getValue()
  record.tab.content = val
  record.tab.isDirty = val !== record.tab.originalContent
}

function getOrCreateModel(tab: EditorTab): monaco.editor.ITextModel {
  let record = tabRecordMap.get(tab.id)
  if (record && !record.model.isDisposed()) {
    record.tab = tab
    return record.model
  }

  if (record && record.model.isDisposed()) {
    tabRecordMap.delete(tab.id)
  }

  const lang = getMonacoLanguage(tab.name || tab.path || tab.language)
  const uri = monaco.Uri.parse(`inmemory://pullman/${tab.id}/${encodeURIComponent(tab.name || 'untitled')}`)
  const existingMonacoModel = monaco.editor.getModel(uri)
  if (existingMonacoModel && !existingMonacoModel.isDisposed()) {
    existingMonacoModel.dispose()
  }

  const model = monaco.editor.createModel(tab.content, lang, uri)
  model.updateOptions({ tabSize: editorSettings.tabSize.value })

  const newRecord: TabModelRecord = {
    tab,
    model,
    changeDebounce: null
  }

  model.onDidChangeContent(() => {
    if (isSwitchingTab) return
    tab.isDirty = true
    if (newRecord.changeDebounce) clearTimeout(newRecord.changeDebounce)
    newRecord.changeDebounce = setTimeout(() => {
      if (!model.isDisposed()) {
        tab.content = model.getValue()
        tab.isDirty = tab.content !== tab.originalContent
      }
    }, 100)
  })

  tabRecordMap.set(tab.id, newRecord)
  return model
}

const defaultEditorOptions: monaco.editor.IStandaloneEditorConstructionOptions = {
  theme: 'pullman-dark', automaticLayout: true, lineHeight: 22, scrollBeyondLastLine: false,
  renderLineHighlight: 'all', cursorBlinking: 'smooth', cursorSmoothCaretAnimation: 'on',
  smoothScrolling: true, bracketPairColorization: { enabled: true },
  guides: { indentation: true, bracketPairs: true }, padding: { top: 10, bottom: 10 },
  roundedSelection: true, fixedOverflowWidgets: true, formatOnPaste: true,
  ...editorSettings.getMonacoOptions()
}

function flushContent(): string {
  if (currentTabId) {
    flushTabRecord(currentTabId)
    const rec = tabRecordMap.get(currentTabId)
    if (rec && !rec.model.isDisposed()) return rec.tab.content
  }
  return props.activeTab?.content || ''
}

async function handleSaveTrigger(asSudo = false): Promise<void> {
  flushContent()
  if (editorSettings.formatOnSave.value && editor) {
    try {
      await editor.getAction('editor.action.formatDocument')?.run()
      flushContent()
    } catch {}
  }
  if (asSudo) emit('save-as-sudo')
  else emit('save')
}

watch(
  () => [
    editorSettings.fontFamily.value, editorSettings.fontSize.value,
    editorSettings.tabSize.value, editorSettings.fontLigatures.value,
    editorSettings.minimap.value, editorSettings.lineNumbers.value, editorSettings.wordWrap.value
  ],
  () => {
    if (editor) {
      editor.updateOptions(editorSettings.getMonacoOptions())
      editor.getModel()?.updateOptions({ tabSize: editorSettings.tabSize.value })
    }
  }
)

function initMonaco(): void {
  if (!containerRef.value || editor) return

  try {
    editor = monaco.editor.create(containerRef.value, defaultEditorOptions)
  } catch (err) {
    console.warn('Failed to create Monaco editor with pullman-dark theme, falling back to vs-dark:', err)
    editor = monaco.editor.create(containerRef.value, { ...defaultEditorOptions, theme: 'vs-dark' })
  }

  // Add Git Blame content widget
  editor.addContentWidget(blameWidget.contentWidget)

  // Track cursor position & cache view state (debounced AST symbol update)
  let cursorSymbolDebounce: ReturnType<typeof setTimeout> | null = null
  editor.onDidChangeCursorPosition((e) => {
    emit('cursor-change', { line: e.position.lineNumber, col: e.position.column })
    blameWidget.update()
    if (cursorSymbolDebounce) clearTimeout(cursorSymbolDebounce)
    cursorSymbolDebounce = setTimeout(() => {
      updateActiveSymbols(e.position.lineNumber, e.position.column)
    }, 120)
    if (!isSwitchingTab && currentTabId && editor) {
      const state = editor.saveViewState()
      if (state) viewStateMap.set(currentTabId, state)
    }
  })

  // Track scroll position to keep blame widget aligned & cache view state
  editor.onDidScrollChange(() => {
    blameWidget.update()
    if (!isSwitchingTab && currentTabId && editor) {
      const state = editor.saveViewState()
      if (state) viewStateMap.set(currentTabId, state)
    }
  })

  // Keyboard Shortcuts: Save, Save as Sudo, AI Gen, Wrap Log, Outline
  editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, () => handleSaveTrigger(false))
  editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyMod.Alt | monaco.KeyCode.KeyS, () => handleSaveTrigger(true))
  editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyK, () => emit('toggle-ai-gen'))
  editor.addCommand(monaco.KeyMod.Alt | monaco.KeyCode.KeyL, () => handleWrapLog())
  editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyMod.Shift | monaco.KeyCode.KeyO, () => { isOutlineModalOpen.value = true })

  // Set model if active tab exists
  if (props.activeTab) {
    const model = getOrCreateModel(props.activeTab)
    editor.setModel(model)
    currentTabId = props.activeTab.id
    const savedState = viewStateMap.get(props.activeTab.id)
    if (savedState) editor.restoreViewState(savedState)
    blameWidget.update()
    updateOutlineSymbols()
  }

  nextTick(() => editor?.layout())

  // Setup ResizeObserver for layout
  resizeObserver = new ResizeObserver(() => {
    editor?.layout()
    blameWidget.update()
  })
  resizeObserver.observe(containerRef.value)
}

function switchTabModel(prevTabId?: string | null): void {
  if (!editor) return

  const oldTabId = prevTabId ?? currentTabId
  const newTab = props.activeTab

  // 1. Flush previous tab content & save its view state
  if (oldTabId && oldTabId !== newTab?.id) {
    flushTabRecord(oldTabId)
    const state = editor.saveViewState()
    if (state) viewStateMap.set(oldTabId, state)
  }

  if (newTab) {
    isSwitchingTab = true
    currentTabId = newTab.id
    const model = getOrCreateModel(newTab)
    if (editor.getModel() !== model) {
      editor.setModel(model)
    }

    // 2. Restore saved view state (scroll position & cursor) or reset to top
    const savedState = viewStateMap.get(newTab.id)
    if (savedState) {
      editor.restoreViewState(savedState)
    } else {
      editor.setScrollTop(0)
      editor.setScrollLeft(0)
      editor.setPosition({ lineNumber: 1, column: 1 })
    }

    // Update language if changed
    const lang = getMonacoLanguage(newTab.name || newTab.path || newTab.language)
    if (model.getLanguageId() !== lang) {
      monaco.editor.setModelLanguage(model, lang)
    }
    editor.focus()
    blameWidget.update()
    updateOutlineSymbols()
    nextTick(() => {
      editor?.layout()
      if (savedState) editor?.restoreViewState(savedState)
      isSwitchingTab = false
    })
    const pos = editor.getPosition()
    if (pos) updateActiveSymbols(pos.lineNumber, pos.column)
  } else {
    currentTabId = null
    isSwitchingTab = false
    activeSymbols.value = []
    outlineSymbols.value = []
    editor.setModel(null)
    blameWidget.update()
  }
}

watch(
  () => props.activeTab?.id,
  (newId, oldId) => {
    if (newId === oldId) return
    if (!editor && containerRef.value) {
      nextTick(() => initMonaco())
    } else {
      switchTabModel(oldId)
    }
  }
)

watch(
  () => props.activeTab?.content,
  (newContent) => {
    if (!editor || !props.activeTab || newContent === undefined || isSwitchingTab) return
    const rec = tabRecordMap.get(props.activeTab.id)
    if (!rec || rec.model.isDisposed()) return
    if (editor.getModel() !== rec.model) return
    if (rec.model.getValue() !== newContent && !props.activeTab.isDirty) {
      rec.model.setValue(newContent)
    }
  }
)

watch(
  () => props.tabs,
  (tabs) => {
    if (!tabs) return
    const openIds = new Set(tabs.map((t) => t.id))
    for (const [id, rec] of tabRecordMap.entries()) {
      if (!openIds.has(id)) {
        if (rec.changeDebounce) clearTimeout(rec.changeDebounce)
        if (!rec.model.isDisposed()) rec.model.dispose()
        tabRecordMap.delete(id)
        viewStateMap.delete(id)
      }
    }
  },
  { deep: true }
)

watch(
  () => props.blame,
  () => {
    blameWidget.update()
  },
  { deep: true }
)

// Public Methods
function goToLine(lineNumber: number): void {
  if (!editor || lineNumber <= 0) return
  editor.revealLineInCenter(lineNumber)
  editor.setPosition({ lineNumber, column: 1 })
  editor.focus()
  blameWidget.update()
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
    if (word) selectedText = word.word
  }

  const statement = createWrapLogStatement(selectedText, props.activeTab.language || 'PHP')
  const line = selection.endLineNumber
  const lineContent = model.getLineContent(line)
  const indent = lineContent.match(/^\s*/)?.[0] || ''
  const insertText = `\n${indent}${statement}`
  const endOfLineCol = model.getLineMaxColumn(line)

  editor.executeEdits('wrap-log', [{
    range: new monaco.Range(line, endOfLineCol, line, endOfLineCol),
    text: insertText,
    forceMoveMarkers: true
  }])
  editor.setPosition({ lineNumber: line + 1, column: indent.length + statement.length + 1 })
  editor.focus()
}

defineExpose({
  goToLine, handleWrapLog, insertSnippet, flushContent,
  formatDocument: async () => { await editor?.getAction('editor.action.formatDocument')?.run() }
})

onMounted(() => {
  blameWidget.domNode.onclick = (e: MouseEvent) => {
    e.stopPropagation()
    const target = e.target as HTMLElement
    const copyBtn = target.closest('[data-blame-action="copy"]') as HTMLElement | null
    if (copyBtn && props.blame?.hash) {
      navigator.clipboard.writeText(props.blame.hash)
      copyBtn.innerText = '✓ Copied'
      setTimeout(() => { if (copyBtn) copyBtn.innerText = 'Copy' }, 1500)
    } else if (target.closest('[data-blame-action="graph"]')) {
      emit('open-git-graph')
    }
  }

  nextTick(() => {
    if (props.activeTab && containerRef.value) initMonaco()
  })
})

onUnmounted(() => {
  resizeObserver?.disconnect()
  try {
    editor?.removeContentWidget(blameWidget.contentWidget)
  } catch {}
  for (const record of tabRecordMap.values()) {
    if (record.changeDebounce) clearTimeout(record.changeDebounce)
    if (!record.model.isDisposed()) record.model.dispose()
  }
  tabRecordMap.clear()
  viewStateMap.clear()
  currentTabId = null
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
