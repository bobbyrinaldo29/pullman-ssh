import { ref, watch } from 'vue'

export interface EditorSettings {
  fontFamily: string
  fontSize: number
  tabSize: number
  fontLigatures: boolean
  minimap: boolean
  lineNumbers: boolean
  wordWrap: boolean
  formatOnSave: boolean
}

export const FONT_FAMILIES = [
  { label: 'JetBrains Mono', value: `'JetBrains Mono', Menlo, Monaco, 'Courier New', monospace` },
  { label: 'Fira Code', value: `'Fira Code', Menlo, Monaco, 'Courier New', monospace` },
  { label: 'Cascadia Code', value: `'Cascadia Code', 'Segoe UI Mono', Menlo, monospace` },
  { label: 'Consolas', value: `Consolas, Menlo, Monaco, monospace` },
  { label: 'System Monospace', value: `Menlo, Monaco, 'Courier New', monospace` }
]

const KEY_FONT_FAMILY = 'app_editor_font_family'
const KEY_FONT_SIZE = 'app_editor_font_size'
const KEY_TAB_SIZE = 'app_editor_tab_size'
const KEY_FONT_LIGATURES = 'app_editor_font_ligatures'
const KEY_MINIMAP = 'app_editor_minimap'
const KEY_LINE_NUMBERS = 'app_editor_line_numbers'
const KEY_WORD_WRAP = 'app_editor_word_wrap'
const KEY_FORMAT_ON_SAVE = 'app_editor_format_on_save'

function getStored<T>(key: string, fallback: T): T {
  if (typeof localStorage === 'undefined') return fallback
  const val = localStorage.getItem(key)
  if (val === null) return fallback
  try {
    return JSON.parse(val) as T
  } catch {
    return fallback
  }
}

// Shared reactive state across components
const fontFamily = ref<string>(
  getStored(KEY_FONT_FAMILY, `'JetBrains Mono', Menlo, Monaco, 'Courier New', monospace`)
)
const fontSize = ref<number>(getStored(KEY_FONT_SIZE, 13))
const tabSize = ref<number>(getStored(KEY_TAB_SIZE, 4))
const fontLigatures = ref<boolean>(getStored(KEY_FONT_LIGATURES, true))
const minimap = ref<boolean>(getStored(KEY_MINIMAP, true))
const lineNumbers = ref<boolean>(getStored(KEY_LINE_NUMBERS, true))
const wordWrap = ref<boolean>(getStored(KEY_WORD_WRAP, true))
const formatOnSave = ref<boolean>(getStored(KEY_FORMAT_ON_SAVE, false))

// Watchers for persistence
watch(fontFamily, (val) => {
  if (typeof localStorage !== 'undefined') localStorage.setItem(KEY_FONT_FAMILY, JSON.stringify(val))
})

watch(fontSize, (val) => {
  const clamped = Math.max(10, Math.min(32, Number(val) || 13))
  if (clamped !== val) fontSize.value = clamped
  if (typeof localStorage !== 'undefined') localStorage.setItem(KEY_FONT_SIZE, JSON.stringify(clamped))
})

watch(tabSize, (val) => {
  if (typeof localStorage !== 'undefined') localStorage.setItem(KEY_TAB_SIZE, JSON.stringify(val))
})

watch(fontLigatures, (val) => {
  if (typeof localStorage !== 'undefined') localStorage.setItem(KEY_FONT_LIGATURES, JSON.stringify(val))
})

watch(minimap, (val) => {
  if (typeof localStorage !== 'undefined') localStorage.setItem(KEY_MINIMAP, JSON.stringify(val))
})

watch(lineNumbers, (val) => {
  if (typeof localStorage !== 'undefined') localStorage.setItem(KEY_LINE_NUMBERS, JSON.stringify(val))
})

watch(wordWrap, (val) => {
  if (typeof localStorage !== 'undefined') localStorage.setItem(KEY_WORD_WRAP, JSON.stringify(val))
})

watch(formatOnSave, (val) => {
  if (typeof localStorage !== 'undefined') localStorage.setItem(KEY_FORMAT_ON_SAVE, JSON.stringify(val))
})

export function useEditorSettings() {
  function getMonacoOptions() {
    return {
      fontFamily: fontFamily.value,
      fontSize: fontSize.value,
      tabSize: tabSize.value,
      fontLigatures: fontLigatures.value,
      minimap: { enabled: minimap.value, maxColumn: 80, scale: 1 },
      lineNumbers: (lineNumbers.value ? 'on' : 'off') as 'on' | 'off',
      wordWrap: (wordWrap.value ? 'on' : 'off') as 'on' | 'off'
    }
  }

  return {
    fontFamily,
    fontSize,
    tabSize,
    fontLigatures,
    minimap,
    lineNumbers,
    wordWrap,
    formatOnSave,
    fontFamilies: FONT_FAMILIES,
    getMonacoOptions
  }
}

