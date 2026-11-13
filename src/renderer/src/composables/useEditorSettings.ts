import { ref, watch, Ref } from 'vue'

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

export type ExternalEditorId = 'internal' | 'vscode' | 'cursor' | 'sublime' | 'notepad++' | 'custom'

export interface MonacoEditorOptions {
  fontFamily: string
  fontSize: number
  tabSize: number
  fontLigatures: boolean
  minimap: { enabled: boolean; maxColumn: number; scale: number }
  lineNumbers: 'on' | 'off'
  wordWrap: 'on' | 'off'
}

export interface UseEditorSettingsReturn {
  fontFamily: Ref<string>
  fontSize: Ref<number>
  tabSize: Ref<number>
  fontLigatures: Ref<boolean>
  minimap: Ref<boolean>
  lineNumbers: Ref<boolean>
  wordWrap: Ref<boolean>
  formatOnSave: Ref<boolean>
  externalEditorType: Ref<ExternalEditorId>
  customEditorPath: Ref<string>
  customEditorArgs: Ref<string>
  openExternalByDefault: Ref<boolean>
  autoSyncExternal: Ref<boolean>
  fontFamilies: typeof FONT_FAMILIES
  getMonacoOptions: () => MonacoEditorOptions
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
const KEY_EXTERNAL_EDITOR_TYPE = 'app_editor_external_type'
const KEY_CUSTOM_EDITOR_PATH = 'app_editor_custom_path'
const KEY_CUSTOM_EDITOR_ARGS = 'app_editor_custom_args'
const KEY_OPEN_EXTERNAL_BY_DEFAULT = 'app_editor_open_external_default'
const KEY_AUTO_SYNC_EXTERNAL = 'app_editor_auto_sync_external'

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

// External Editor Preferences
const externalEditorType = ref<ExternalEditorId>(getStored(KEY_EXTERNAL_EDITOR_TYPE, 'internal'))
const customEditorPath = ref<string>(getStored(KEY_CUSTOM_EDITOR_PATH, ''))
const customEditorArgs = ref<string>(getStored(KEY_CUSTOM_EDITOR_ARGS, ''))
const openExternalByDefault = ref<boolean>(getStored(KEY_OPEN_EXTERNAL_BY_DEFAULT, false))
const autoSyncExternal = ref<boolean>(getStored(KEY_AUTO_SYNC_EXTERNAL, true))

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

watch(externalEditorType, (val) => {
  if (typeof localStorage !== 'undefined') localStorage.setItem(KEY_EXTERNAL_EDITOR_TYPE, JSON.stringify(val))
})

watch(customEditorPath, (val) => {
  if (typeof localStorage !== 'undefined') localStorage.setItem(KEY_CUSTOM_EDITOR_PATH, JSON.stringify(val))
})

watch(customEditorArgs, (val) => {
  if (typeof localStorage !== 'undefined') localStorage.setItem(KEY_CUSTOM_EDITOR_ARGS, JSON.stringify(val))
})

watch(openExternalByDefault, (val) => {
  if (typeof localStorage !== 'undefined') localStorage.setItem(KEY_OPEN_EXTERNAL_BY_DEFAULT, JSON.stringify(val))
})

watch(autoSyncExternal, (val) => {
  if (typeof localStorage !== 'undefined') localStorage.setItem(KEY_AUTO_SYNC_EXTERNAL, JSON.stringify(val))
})

export function useEditorSettings(): UseEditorSettingsReturn {
  function getMonacoOptions(): MonacoEditorOptions {
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
    externalEditorType,
    customEditorPath,
    customEditorArgs,
    openExternalByDefault,
    autoSyncExternal,
    fontFamilies: FONT_FAMILIES,
    getMonacoOptions
  }
}

