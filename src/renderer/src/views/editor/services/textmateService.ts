import * as monaco from 'monaco-editor'
import { createHighlighter, type Highlighter, type ThemeRegistrationAny } from 'shiki'
import { shikiToMonaco } from '@shikijs/monaco'

let highlighterPromise: Promise<Highlighter> | null = null

export const SUPPORTED_TEXTMATE_LANGUAGES = [
  'php',
  'javascript',
  'typescript',
  'html',
  'css',
  'scss',
  'less',
  'json',
  'sql',
  'vue',
  'python',
  'shell',
  'yaml',
  'markdown',
  'xml'
] as const

/**
 * Pullman Dark theme specification matching VS Code One Dark Pro / GitHub Dark
 * with Pullman's dark slate `#1E222B` background and `#252B3A` highlights.
 */
export const pullmanDarkShikiTheme: ThemeRegistrationAny = {
  name: 'pullman-dark',
  type: 'dark',
  colors: {
    'editor.background': '#1E222B',
    'editorGutter.background': '#1E222B',
    'editorLineNumber.foreground': '#4b5263',
    'editorLineNumber.activeForeground': '#abb2bf',
    'editor.lineHighlightBackground': '#252B3A',
    'editorCursor.foreground': '#528bff',
    'editor.selectionBackground': '#3E4451',
    'editor.inactiveSelectionBackground': '#2c313c',

    // Soft GitHub-style diff colors
    'diffEditor.insertedTextBackground': '#2ea04338',
    'diffEditor.removedTextBackground': '#f8514938',
    'diffEditor.insertedLineBackground': '#2ea0431a',
    'diffEditor.removedLineBackground': '#f851491a',
    'diffEditor.insertedTextBorder': '#00000000',
    'diffEditor.removedTextBorder': '#00000000',
    'diffEditorGutter.insertedLineBackground': '#2ea04330',
    'diffEditorGutter.removedLineBackground': '#f8514930',
    'diffEditorOverview.insertedForeground': '#2ea04399',
    'diffEditorOverview.removedForeground': '#f8514999',
    'diffEditor.diagonalFill': '#252B3A80'
  },
  tokenColors: [
    { settings: { foreground: '#abb2bf' } },
    { scope: ['comment', 'punctuation.definition.comment'], settings: { foreground: '#5c6370', fontStyle: 'italic' } },
    { scope: ['keyword', 'keyword.control', 'storage', 'storage.type', 'storage.modifier'], settings: { foreground: '#c678dd' } },
    { scope: ['string', 'string.quoted', 'string.template'], settings: { foreground: '#98c379' } },
    { scope: ['constant.numeric', 'number'], settings: { foreground: '#d19a66' } },
    { scope: ['constant.language', 'constant.character'], settings: { foreground: '#d19a66' } },
    { scope: ['entity.name.function', 'support.function', 'meta.function-call'], settings: { foreground: '#61afef' } },
    { scope: ['entity.name.type', 'entity.name.class', 'support.type', 'support.class', 'entity.other.inherited-class'], settings: { foreground: '#e5c07b' } },
    { scope: ['variable', 'variable.parameter', 'variable.language', 'variable.other'], settings: { foreground: '#e06c75' } },
    { scope: ['punctuation', 'meta.brace', 'punctuation.section'], settings: { foreground: '#abb2bf' } },
    { scope: ['entity.other.attribute-name', 'entity.name.tag'], settings: { foreground: '#e06c75' } }
  ]
}

/**
 * Initializes VS Code TextMate syntax highlighting powered by Shiki & Oniguruma Wasm.
 * Replaces Monaco's basic Monarch tokenizers with 100% authentic VS Code syntax highlighting.
 */
export async function initTextmateService(monacoInstance: typeof monaco): Promise<Highlighter> {
  if (highlighterPromise) return highlighterPromise

  highlighterPromise = (async () => {
    try {
      const highlighter = await createHighlighter({
        themes: [pullmanDarkShikiTheme, 'one-dark-pro', 'github-dark'],
        langs: [...SUPPORTED_TEXTMATE_LANGUAGES]
      })

      // Register TextMate tokens provider into Monaco for all loaded languages
      shikiToMonaco(highlighter, monacoInstance)

      // Guard monaco.editor.setTheme against any unrecognized theme name
      const originalSetTheme = monacoInstance.editor.setTheme.bind(monacoInstance.editor)
      monacoInstance.editor.setTheme = (themeName: string) => {
        try {
          originalSetTheme(themeName)
        } catch (err) {
          console.warn(`[TextMate] Fallback for theme "${themeName}":`, err)
          try {
            originalSetTheme('vs-dark')
          } catch {}
        }
      }

      // Explicitly set theme to our loaded pullman-dark theme
      monacoInstance.editor.setTheme('pullman-dark')
      return highlighter
    } catch (err) {
      console.warn('Failed to initialize TextMate highlighter, falling back to Monarch:', err)
      throw err
    }
  })()

  return highlighterPromise
}

