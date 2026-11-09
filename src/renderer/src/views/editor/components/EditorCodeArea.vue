<script setup lang="ts">
import { ref, computed, watch, onMounted, nextTick } from 'vue'
import { Code, Save, GitCommit } from 'lucide-vue-next'
import { EditorTab, EditorCursorPos, GitBlameInfo } from '../types'
import { useIntelephense } from '../intelephense/useIntelephense'
import { highlightPhpCode } from '../intelephense/phpHighlighter'
import IntelephensePopup from '../intelephense/IntelephensePopup.vue'
import { PhpSuggestion } from '../intelephense/phpDictionary'
import { insertWrapLogStatement } from '../utils/wrapLog'
import { useEditorShortcuts } from '../composables/useEditorShortcuts'

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

const textareaRef = ref<HTMLTextAreaElement | null>(null)
const gutterRef = ref<HTMLElement | null>(null)
const syntaxPreRef = ref<HTMLElement | null>(null)

const {
  isOpen,
  suggestions,
  selectedIndex,
  popupCoords,
  activeSuggestion,
  syntaxErrors,
  triggerCompletion,
  selectNext,
  selectPrev,
  applyCompletion,
  checkSyntax,
  close: closeIntelephense
} = useIntelephense()

const { resetHistory, recordState, processKeyDown } = useEditorShortcuts()

const lineCount = computed(() => props.activeTab ? props.activeTab.content.split('\n').length : 0)
const isPhp = computed(() => props.activeTab?.language === 'PHP')
const highlightedPhp = computed(() => {
  if (!props.activeTab || !isPhp.value || props.activeTab.content.length > 300000) return ''
  return highlightPhpCode(props.activeTab.content)
})

const scrollTop = ref(0)
const scrollLeft = ref(0)
const currentLine = ref(1)

const activeLineText = computed(() => {
  if (!props.activeTab || currentLine.value <= 0) return ''
  const lines = props.activeTab.content.split('\n')
  return lines[currentLine.value - 1] || ''
})

const activeLineVisible = computed(() => {
  if (!props.blame || !textareaRef.value || currentLine.value <= 0) return false
  // Do not show inline blame on empty or whitespace-only lines
  if (!activeLineText.value.trim()) return false
  const top = 12 + (currentLine.value - 1) * 22 - scrollTop.value
  const maxH = textareaRef.value.clientHeight || 500
  return top >= 0 && top <= (maxH - 22)
})

const blameGhostStyle = computed(() => {
  if (!activeLineVisible.value) return { display: 'none' }
  const top = 12 + (currentLine.value - 1) * 22 - scrollTop.value
  const left = 12 + Math.round(activeLineText.value.replace(/\t/g, '  ').length * 7.82) + 24 - scrollLeft.value
  return { top: `${top}px`, left: `${Math.max(12, left)}px` }
})

function handleScroll(): void {
  if (textareaRef.value) {
    scrollTop.value = textareaRef.value.scrollTop
    scrollLeft.value = textareaRef.value.scrollLeft
    if (gutterRef.value) gutterRef.value.scrollTop = scrollTop.value
    if (syntaxPreRef.value) {
      syntaxPreRef.value.scrollTop = scrollTop.value
      syntaxPreRef.value.scrollLeft = scrollLeft.value
    }
  }
}

function handleInput(e: Event): void {
  const target = e.target as HTMLTextAreaElement
  if (!props.activeTab) return

  props.activeTab.content = target.value
  props.activeTab.isDirty = props.activeTab.content !== props.activeTab.originalContent
  recordState(target.value, target.selectionStart, false)
  updateCursorPosition()
  handleScroll()

  // Run PHP Intelephense Linting & Suggestion engine
  if (isPhp.value) {
    checkSyntax(props.activeTab.content, 'PHP')
    emit('diagnostics-change', syntaxErrors.value)
    triggerCompletion(target, props.activeTab.content, 'PHP')
  }
}

function handleKeyDown(e: KeyboardEvent): void {
  // If Intelephense popup is active, intercept arrow and confirm keys
  if (isOpen.value) {
    if (e.key === 'ArrowDown') { e.preventDefault(); selectNext(); return }
    if (e.key === 'ArrowUp') { e.preventDefault(); selectPrev(); return }
    if (e.key === 'Enter' || e.key === 'Tab') { e.preventDefault(); handleApplySuggestion(); return }
    if (e.key === 'Escape') { e.preventDefault(); closeIntelephense(); return }
  }

  // VS Code editing shortcuts: Undo, Redo, Comment, Move Line, Duplicate Line, Delete Line
  if (textareaRef.value && props.activeTab) {
    const handled = processKeyDown(e, textareaRef.value, props.activeTab, () => {
      updateCursorPosition()
      handleScroll()
      if (isPhp.value && props.activeTab) {
        checkSyntax(props.activeTab.content, 'PHP')
        emit('diagnostics-change', syntaxErrors.value)
      }
    })
    if (handled) return
  }

  // Wrap Log shortcut (Option+L or Alt+L)
  if (e.altKey && (e.key === 'l' || e.key === 'L' || e.code === 'KeyL' || e.key === '¬')) {
    e.preventDefault()
    handleWrapLog()
    return
  }

  // Antigravity AI Gen shortcut (Cmd+K or Ctrl+K)
  if ((e.metaKey || e.ctrlKey) && (e.key === 'k' || e.key === 'K')) {
    e.preventDefault()
    emit('toggle-ai-gen')
    return
  }

  // Save as Sudo shortcut (Cmd+Option+S or Ctrl+Alt+S)
  if ((e.metaKey || e.ctrlKey) && e.altKey && (e.key === 's' || e.key === 'S')) {
    e.preventDefault()
    emit('save-as-sudo')
    return
  }

  // Save shortcut (Cmd+S or Ctrl+S)
  if ((e.metaKey || e.ctrlKey) && e.key === 's') {
    e.preventDefault()
    emit('save')
    return
  }

  // Trigger IntelliSense manually (Ctrl+Space)
  if ((e.ctrlKey || e.metaKey) && e.key === ' ') {
    e.preventDefault()
    if (textareaRef.value && props.activeTab && isPhp.value) {
      triggerCompletion(textareaRef.value, props.activeTab.content, 'PHP')
    }
    return
  }

  // Tab key indentation
  if (e.key === 'Tab') {
    e.preventDefault()
    const textarea = textareaRef.value
    if (!textarea || !props.activeTab) return

    const start = textarea.selectionStart
    const end = textarea.selectionEnd
    const val = props.activeTab.content

    props.activeTab.content = val.substring(0, start) + '  ' + val.substring(end)
    props.activeTab.isDirty = props.activeTab.content !== props.activeTab.originalContent
    recordState(props.activeTab.content, start + 2, true)

    nextTick(() => {
      textarea.selectionStart = textarea.selectionEnd = start + 2
      updateCursorPosition()
      handleScroll()
    })
  }
}

function handleApplySuggestion(suggestion?: PhpSuggestion): void {
  const textarea = textareaRef.value
  if (!textarea || !props.activeTab) return

  if (suggestion) {
    const item = suggestion
    const start = textarea.selectionStart
    const newContent =
      props.activeTab.content.substring(0, start) +
      item.insertText +
      props.activeTab.content.substring(start)
    props.activeTab.content = newContent
    props.activeTab.isDirty = true
    recordState(newContent, start + item.insertText.length, true)
    closeIntelephense()
    return
  }

  const result = applyCompletion(props.activeTab.content)
  if (result) {
    props.activeTab.content = result.newContent
    props.activeTab.isDirty = props.activeTab.content !== props.activeTab.originalContent
    recordState(result.newContent, result.newCursor, true)
    nextTick(() => {
      textarea.selectionStart = textarea.selectionEnd = result.newCursor
      updateCursorPosition()
      handleScroll()
      if (props.activeTab && isPhp.value) {
        checkSyntax(props.activeTab.content, 'PHP')
        emit('diagnostics-change', syntaxErrors.value)
      }
    })
  }
}

function updateCursorPosition(): void {
  const textarea = textareaRef.value
  if (!textarea || !props.activeTab) return

  const pos = textarea.selectionStart
  const textBefore = props.activeTab.content.substring(0, pos)
  const lines = textBefore.split('\n')
  const line = lines.length
  const col = lines[lines.length - 1].length + 1

  currentLine.value = line
  emit('cursor-change', { line, col })
}

watch(
  () => props.cursorPos?.line,
  (l) => {
    if (l && l > 0 && l !== currentLine.value) {
      currentLine.value = l
    }
  }
)

const activeHighlightLine = ref<number | null>(null)

function goToLine(lineNumber: number): void {
  if (!props.activeTab || lineNumber <= 0) return
  const lines = props.activeTab.content.split('\n')
  const targetIndex = Math.max(0, Math.min(lineNumber - 1, lines.length - 1))

  let charOffset = 0
  for (let i = 0; i < targetIndex; i++) {
    charOffset += lines[i].length + 1
  }

  activeHighlightLine.value = lineNumber
  setTimeout(() => {
    activeHighlightLine.value = null
  }, 2500)

  nextTick(() => {
    const textarea = textareaRef.value
    if (textarea) {
      textarea.focus()
      textarea.selectionStart = charOffset
      textarea.selectionEnd = charOffset

      const lineHeight = 22
      const targetScrollTop = Math.max(0, targetIndex * lineHeight - textarea.clientHeight / 2 + 12)
      textarea.scrollTop = targetScrollTop

      handleScroll()
      updateCursorPosition()
    }
  })
}

function handleWrapLog(): void {
  const textarea = textareaRef.value
  if (!textarea || !props.activeTab) return

  const { newContent, newCursor } = insertWrapLogStatement(
    props.activeTab.content,
    textarea.selectionStart,
    textarea.selectionEnd,
    props.activeTab.language
  )

  props.activeTab.content = newContent
  props.activeTab.isDirty = newContent !== props.activeTab.originalContent
  recordState(newContent, newCursor, true)

  nextTick(() => {
    textarea.selectionStart = textarea.selectionEnd = newCursor
    textarea.focus()
    updateCursorPosition()
    handleScroll()
    if (isPhp.value && props.activeTab) {
      checkSyntax(props.activeTab.content, 'PHP')
      emit('diagnostics-change', syntaxErrors.value)
    }
  })
}

function insertSnippet(code: string): void {
  const textarea = textareaRef.value
  if (!textarea || !props.activeTab) return
  const start = textarea.selectionStart
  const end = textarea.selectionEnd
  const newContent = props.activeTab.content.substring(0, start) + code + props.activeTab.content.substring(end)
  props.activeTab.content = newContent
  props.activeTab.isDirty = true
  recordState(newContent, start + code.length, true)
  nextTick(() => {
    textarea.selectionStart = textarea.selectionEnd = start + code.length
    textarea.focus()
    updateCursorPosition()
    handleScroll()
  })
}

defineExpose({
  goToLine,
  handleWrapLog,
  insertSnippet
})

watch(
  () => props.activeTab?.id,
  () => {
    closeIntelephense()
    resetHistory(props.activeTab?.content || '')
    emit('cursor-change', { line: 1, col: 1 })
    if (props.activeTab && isPhp.value) {
      checkSyntax(props.activeTab.content, 'PHP')
      emit('diagnostics-change', syntaxErrors.value)
    } else {
      emit('diagnostics-change', [])
    }
    nextTick(() => handleScroll())
  }
)

onMounted(() => {
  resetHistory(props.activeTab?.content || '')
  handleScroll()
  updateCursorPosition()
  if (props.activeTab && isPhp.value) {
    checkSyntax(props.activeTab.content, 'PHP')
    emit('diagnostics-change', syntaxErrors.value)
  }
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
      <p class="text-xs text-[#848D97] mt-1.5 max-w-sm leading-relaxed">
        Select a file from the Explorer on the left to start editing remote code via SSH.
      </p>

      <!-- Keyboard shortcuts hints -->
      <div class="mt-6 border border-[#2B3245] rounded-xl bg-[#181A20] p-4 text-xs text-[#848D97] space-y-1.5 text-left w-80">
        <div class="flex items-center justify-between">
          <span class="text-purple-300 font-medium">Antigravity AI Gen</span>
          <span class="px-1.5 py-0.5 bg-purple-600/20 border border-purple-500/40 rounded text-purple-300 font-mono text-[11px]">⌘K</span>
        </div>
        <div class="flex items-center justify-between">
          <span>Undo / Redo</span>
          <span class="px-1.5 py-0.5 bg-[#252A36] border border-[#32394C] rounded text-slate-300 font-mono text-[11px]">⌘Z / ⇧⌘Z</span>
        </div>
        <div class="flex items-center justify-between">
          <span>Toggle Comment</span>
          <span class="px-1.5 py-0.5 bg-[#252A36] border border-[#32394C] rounded text-slate-300 font-mono text-[11px]">⌘/</span>
        </div>
        <div class="flex items-center justify-between">
          <span>Move / Duplicate Line</span>
          <span class="px-1.5 py-0.5 bg-[#252A36] border border-[#32394C] rounded text-slate-300 font-mono text-[11px]">⌥↑↓ &bull; ⇧⌥↓</span>
        </div>
        <div class="flex items-center justify-between">
          <span>Save to Remote SSH</span>
          <span class="px-1.5 py-0.5 bg-[#252A36] border border-[#32394C] rounded text-slate-300 font-mono text-[11px]">⌘S</span>
        </div>
        <div class="flex items-center justify-between">
          <span>Wrap Log (var_dump / log)</span>
          <span class="px-1.5 py-0.5 bg-[#252A36] border border-[#32394C] rounded text-slate-300 font-mono text-[11px]">⌥L</span>
        </div>
      </div>
    </div>

    <!-- Active File Editor Canvas -->
    <div v-else class="flex-1 flex overflow-hidden relative">
      <!-- Line Numbers Gutter -->
      <div
        ref="gutterRef"
        class="w-12 bg-[#1E222B] border-r border-[#24272E] text-[#4E5666] select-none text-right pr-3 py-3 overflow-hidden leading-[22px] text-[13px] font-mono shrink-0"
      >
        <div
          v-for="n in lineCount"
          :key="n"
          class="h-[22px] transition-colors"
          :class="activeHighlightLine === n ? 'text-amber-300 font-bold bg-amber-500/20 rounded-l' : ''"
        >
          {{ n }}
        </div>
      </div>

      <!-- Editor Canvas Wrapper -->
      <div class="flex-1 h-full relative overflow-hidden bg-[#1E222B]">
        <!-- Syntax Highlighting Underlay (for PHP) -->
        <pre
          v-if="isPhp && highlightedPhp"
          ref="syntaxPreRef"
          class="editor-code-layer absolute inset-0 overflow-hidden pointer-events-none select-none text-[#D4D4D4]"
          aria-hidden="true"
          v-html="highlightedPhp"
        ></pre>

        <!-- Editable Textarea -->
        <textarea
          ref="textareaRef"
          :value="activeTab.content"
          class="editor-code-layer absolute inset-0 w-full h-full resize-none focus:outline-none overflow-auto font-normal"
          :class="isPhp && highlightedPhp ? 'text-transparent bg-transparent caret-[#528BFF]' : 'text-[#D4D4D4] bg-[#1E222B]'"
          spellcheck="false"
          autocomplete="off"
          autocorrect="off"
          autocapitalize="off"
          @input="handleInput"
          @scroll="handleScroll"
          @keydown="handleKeyDown"
          @click="updateCursorPosition"
          @keyup="updateCursorPosition"
        ></textarea>

        <!-- Inline Git Blame Ghost Text (VS Code / GitLens style) -->
        <div
          v-if="blame && activeLineVisible"
          class="absolute pointer-events-none select-none z-10 flex items-center space-x-1.5 font-mono text-[11px] leading-[22px] h-[22px] text-slate-400 whitespace-nowrap opacity-65"
          :style="blameGhostStyle"
        >
          <GitCommit class="w-3.5 h-3.5 text-cyan-400/80 shrink-0 not-italic" />
          <span class="truncate max-w-[500px]">
            <span class="font-medium text-slate-300/90">{{ blame.author }}</span>,
            <span class="text-slate-400/75">{{ blame.timeAgo }}</span>
            <span class="text-slate-500/60 mx-1.5">•</span>
            <span class="text-slate-400/75 italic">{{ blame.summary }}</span>
          </span>
        </div>

        <!-- Intelephense Autocomplete Floating Popup -->
        <IntelephensePopup
          v-if="isOpen"
          :suggestions="suggestions"
          :selected-index="selectedIndex"
          :active-suggestion="activeSuggestion"
          :coords="popupCoords"
          @select="handleApplySuggestion"
        />
      </div>

      <!-- Saving Spinner Overlay -->
      <div
        v-if="activeTab.isSaving"
        class="absolute top-3 right-4 bg-blue-600/90 text-white text-xs px-2.5 py-1 rounded-md shadow-lg flex items-center space-x-1.5 select-none pointer-events-none animate-pulse z-40"
      >
        <Save class="w-3.5 h-3.5" />
        <span>Saving to remote...</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.editor-code-layer {
  font-family: 'JetBrains Mono', 'Fira Code', 'Cascadia Code', Menlo, Monaco, Consolas, monospace;
  font-size: 13px; line-height: 22px; letter-spacing: 0; word-spacing: 0;
  tab-size: 2; white-space: pre; word-wrap: normal; box-sizing: border-box;
  padding: 12px; margin: 0; border: 0;
}
.editor-code-layer::selection,
.editor-code-layer::-moz-selection {
  background-color: #264F78 !important; color: #FFFFFF !important; -webkit-text-fill-color: #FFFFFF !important;
}
</style>
