import * as monaco from 'monaco-editor'
import editorWorker from 'monaco-editor/editor/editor.worker?worker'
import jsonWorker from 'monaco-editor/language/json/json.worker?worker'
import cssWorker from 'monaco-editor/language/css/css.worker?worker'
import htmlWorker from 'monaco-editor/language/html/html.worker?worker'
import tsWorker from 'monaco-editor/language/typescript/ts.worker?worker'

// Configure Monaco Environment workers for language services and diff computation
self.MonacoEnvironment = {
  getWorker(_: any, label: string) {
    if (label === 'json') return new jsonWorker()
    if (label === 'css' || label === 'scss' || label === 'less') return new cssWorker()
    if (label === 'html' || label === 'handlebars' || label === 'razor') return new htmlWorker()
    if (label === 'typescript' || label === 'javascript') return new tsWorker()
    return new editorWorker()
  }
}

// Define Pullman dark theme matching the app UI
monaco.editor.defineTheme('pullman-dark', {
  base: 'vs-dark',
  inherit: true,
  rules: [
    { token: '', foreground: 'abb2bf', background: '1E222B' },
    { token: 'comment', foreground: '5c6370', fontStyle: 'italic' },
    { token: 'keyword', foreground: 'c678dd' },
    { token: 'string', foreground: '98c379' },
    { token: 'number', foreground: 'd19a66' },
    { token: 'regexp', foreground: 'e06c75' },
    { token: 'type', foreground: 'e5c07b' },
    { token: 'class', foreground: 'e5c07b' },
    { token: 'function', foreground: '61afef' },
    { token: 'variable', foreground: 'e06c75' }
  ],
  colors: {
    'editor.background': '#1E222B',
    'editorGutter.background': '#1E222B',
    'editorLineNumber.foreground': '#4b5263',
    'editorLineNumber.activeForeground': '#abb2bf',
    'editor.lineHighlightBackground': '#252B3A',
    'editorCursor.foreground': '#528bff',
    'editor.selectionBackground': '#3E4451',
    'editor.inactiveSelectionBackground': '#2c313c',

    // Soft & Pleasant GitHub-style Diff Editor Colors
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
  }
})

export function getMonacoLanguage(languageOrFilename?: string): string {
  if (!languageOrFilename) return 'plaintext'
  const ext = languageOrFilename.includes('.')
    ? languageOrFilename.split('.').pop()?.toLowerCase() || ''
    : languageOrFilename.toLowerCase()

  const map: Record<string, string> = {
    js: 'javascript',
    javascript: 'javascript',
    ts: 'typescript',
    typescript: 'typescript',
    json: 'json',
    html: 'html',
    css: 'css',
    scss: 'scss',
    less: 'less',
    php: 'php',
    py: 'python',
    python: 'python',
    sh: 'shell',
    bash: 'shell',
    shell: 'shell',
    'shell script': 'shell',
    sql: 'sql',
    md: 'markdown',
    markdown: 'markdown',
    xml: 'xml',
    yml: 'yaml',
    yaml: 'yaml',
    dockerfile: 'dockerfile',
    ini: 'ini',
    properties: 'ini',
    vue: 'html'
  }

  return map[ext] || 'plaintext'
}

export { monaco }
