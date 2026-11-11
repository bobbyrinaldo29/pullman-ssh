import * as monaco from 'monaco-editor'

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
    'editor.inactiveSelectionBackground': '#2c313c'
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
