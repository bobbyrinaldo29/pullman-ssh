<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { Columns2, AlignJustify, ChevronUp, ChevronDown, FileCode } from 'lucide-vue-next'
import { monaco, getMonacoLanguage } from '../monaco/monacoSetup'
import { parseUnifiedDiff } from '../utils/diffParser'
import { useEditorSettings } from '../../../composables/useEditorSettings'

const props = withDefaults(
  defineProps<{
    original?: string
    modified?: string
    diffContent?: string
    filename?: string
    language?: string
    readOnly?: boolean
    hideHeader?: boolean
  }>(),
  {
    original: '',
    modified: '',
    diffContent: '',
    filename: '',
    language: '',
    readOnly: true,
    hideHeader: false
  }
)

const diffContainerRef = ref<HTMLDivElement | null>(null)
let diffEditor: monaco.editor.IStandaloneDiffEditor | null = null
let originalModel: monaco.editor.ITextModel | null = null
let modifiedModel: monaco.editor.ITextModel | null = null
const editorSettings = useEditorSettings()

const isInline = ref(false)
const changesCount = ref(0)

const cleanFilename = computed(() => {
  return (props.filename || '').replace(/\s*\(Diff\)/i, '').trim()
})

const computedTexts = computed(() => {
  if (props.original || props.modified) {
    return { original: props.original, modified: props.modified }
  }
  if (props.diffContent) {
    return parseUnifiedDiff(props.diffContent)
  }
  return { original: '', modified: '' }
})

const detectedLanguage = computed(() => {
  if (props.language && props.language !== 'diff') return getMonacoLanguage(props.language)
  if (cleanFilename.value) return getMonacoLanguage(cleanFilename.value)
  return 'plaintext'
})

function updateModels(): void {
  if (!diffEditor) return

  // Dispose old models
  if (originalModel && !originalModel.isDisposed()) originalModel.dispose()
  if (modifiedModel && !modifiedModel.isDisposed()) modifiedModel.dispose()

  const lang = detectedLanguage.value
  const origUri = monaco.Uri.parse(`inmemory://diff-orig/${Date.now()}/${encodeURIComponent(cleanFilename.value || 'original')}`)
  const modUri = monaco.Uri.parse(`inmemory://diff-mod/${Date.now()}/${encodeURIComponent(cleanFilename.value || 'modified')}`)

  originalModel = monaco.editor.createModel(computedTexts.value.original, lang, origUri)
  modifiedModel = monaco.editor.createModel(computedTexts.value.modified, lang, modUri)

  diffEditor.setModel({
    original: originalModel,
    modified: modifiedModel
  })
}

function initDiffEditor(): void {
  if (!diffContainerRef.value || diffEditor) return

  try {
    diffEditor = monaco.editor.createDiffEditor(diffContainerRef.value, {
      theme: 'pullman-dark',
      automaticLayout: true,
      readOnly: props.readOnly,
      renderSideBySide: !isInline.value,
      originalEditable: false,
      fontSize: editorSettings.fontSize.value,
      fontFamily: editorSettings.fontFamily.value,
      fontLigatures: editorSettings.fontLigatures.value,
      lineHeight: 20,
      minimap: { enabled: false },
      scrollBeyondLastLine: false,
      diffWordWrap: editorSettings.wordWrap.value ? 'on' : 'off',
      wordWrap: editorSettings.wordWrap.value ? 'on' : 'off',
      renderIndicators: true,
      smoothScrolling: true,
      ignoreTrimWhitespace: false,
      enableSplitViewResizing: true,
      hideUnchangedRegions: {
        enabled: true,
        revealLineCount: 20,
        minimumLineCount: 3
      }
    })
  } catch (err) {
    console.warn('Failed to create diff editor with pullman-dark theme, falling back to vs-dark:', err)
    diffEditor = monaco.editor.createDiffEditor(diffContainerRef.value, {
      theme: 'vs-dark',
      automaticLayout: true,
      readOnly: props.readOnly,
      renderSideBySide: !isInline.value
    })
  }

  diffEditor.onDidUpdateDiff(() => {
    const changes = diffEditor?.getLineChanges() || []
    changesCount.value = changes.length
    if (changes.length > 0) {
      const first = changes[0]
      const targetLine = first.modifiedStartLineNumber || first.originalStartLineNumber || 1
      diffEditor?.getModifiedEditor().revealLineInCenter(targetLine)
      diffEditor?.getOriginalEditor().revealLineInCenter(targetLine)
    }
  })

  updateModels()
}

function toggleInlineView(): void {
  isInline.value = !isInline.value
  diffEditor?.updateOptions({
    renderSideBySide: !isInline.value
  })
}

function nextChange(): void {
  diffEditor?.goToDiff('next')
}

function prevChange(): void {
  diffEditor?.goToDiff('previous')
}

watch(
  [() => props.original, () => props.modified, () => props.diffContent, () => props.filename],
  () => {
    nextTick(() => {
      if (diffEditor) updateModels()
    })
  }
)

watch(
  () => [
    editorSettings.fontFamily.value,
    editorSettings.fontSize.value,
    editorSettings.fontLigatures.value,
    editorSettings.lineNumbers.value,
    editorSettings.wordWrap.value
  ],
  () => {
    if (diffEditor) {
      diffEditor.updateOptions({
        fontFamily: editorSettings.fontFamily.value,
        fontSize: editorSettings.fontSize.value,
        fontLigatures: editorSettings.fontLigatures.value,
        lineNumbers: editorSettings.lineNumbers.value ? 'on' : 'off',
        diffWordWrap: editorSettings.wordWrap.value ? 'on' : 'off',
        wordWrap: editorSettings.wordWrap.value ? 'on' : 'off'
      })
    }
  }
)

onMounted(() => {
  nextTick(() => {
    initDiffEditor()
  })
})

onUnmounted(() => {
  if (originalModel && !originalModel.isDisposed()) originalModel.dispose()
  if (modifiedModel && !modifiedModel.isDisposed()) modifiedModel.dispose()
  diffEditor?.dispose()
  diffEditor = null
})
</script>

<template>
  <div class="flex-1 flex flex-col h-full bg-[#1E222B] overflow-hidden select-none">
    <!-- Diff Header Toolbar -->
    <div
      v-if="!hideHeader"
      class="h-7 px-3 bg-[#181A1F] border-b border-[#24272E] flex items-center justify-between text-xs shrink-0 select-none"
    >
      <div class="flex items-center space-x-2 truncate">
        <FileCode class="w-3.5 h-3.5 text-blue-400 shrink-0" />
        <span class="text-slate-300 font-medium truncate text-[11px]">{{ filename || 'Diff Viewer' }}</span>
        <span class="text-[10px] text-slate-500 font-mono">({{ detectedLanguage }})</span>
        <span
          v-if="changesCount > 0"
          class="px-1.5 py-0.2 rounded text-[10px] font-mono bg-blue-500/20 text-blue-300 border border-blue-500/30 shrink-0"
        >
          {{ changesCount }} {{ changesCount === 1 ? 'change' : 'changes' }}
        </span>
        <span
          v-else
          class="text-[10px] text-slate-500 font-mono shrink-0"
        >
          (No changes)
        </span>
      </div>

      <!-- Controls: Toggle Inline/Split, Navigate Changes -->
      <div class="flex items-center space-x-1 shrink-0">
        <button
          type="button"
          class="p-1 rounded text-slate-400 hover:text-white hover:bg-[#252A36] transition-colors"
          title="Previous Change"
          @click="prevChange"
        >
          <ChevronUp class="w-3.5 h-3.5" />
        </button>
        <button
          type="button"
          class="p-1 rounded text-slate-400 hover:text-white hover:bg-[#252A36] transition-colors"
          title="Next Change"
          @click="nextChange"
        >
          <ChevronDown class="w-3.5 h-3.5" />
        </button>
        <div class="h-3 w-px bg-[#2D3547] mx-1"></div>
        <button
          type="button"
          class="px-2 py-0.5 rounded text-[11px] font-medium flex items-center space-x-1 transition-colors"
          :class="isInline ? 'bg-blue-600/20 text-blue-300 border border-blue-500/30' : 'text-slate-400 hover:text-white hover:bg-[#252A36]'"
          :title="isInline ? 'Switch to Side-by-Side View' : 'Switch to Inline View'"
          @click="toggleInlineView"
        >
          <component :is="isInline ? AlignJustify : Columns2" class="w-3 h-3" />
          <span>{{ isInline ? 'Inline' : 'Side-by-Side' }}</span>
        </button>
      </div>
    </div>

    <!-- Monaco Diff Editor Host Container -->
    <div ref="diffContainerRef" class="flex-1 w-full h-full min-h-0 overflow-hidden"></div>
  </div>
</template>

