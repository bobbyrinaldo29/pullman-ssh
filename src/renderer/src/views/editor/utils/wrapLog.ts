/**
 * Wrap Log Utility for PHP and other languages (VS Code wrap-log style).
 * Generates formatted debug log statements for variables or expressions.
 */

export function extractTargetWord(content: string, selStart: number, selEnd: number): string {
  const directSelection = content.substring(selStart, selEnd).trim()
  if (directSelection) {
    return directSelection
  }

  let start = selStart
  let end = selStart

  // Scan backwards
  while (start > 0) {
    const prevChar = content[start - 1]
    if ('\n\r;(),= '.includes(prevChar)) break
    if (/[\w$>\-'"]/.test(prevChar)) {
      start--
    } else {
      break
    }
  }

  // Scan forwards
  while (end < content.length) {
    const nextChar = content[end]
    if ('\n\r;(),= '.includes(nextChar)) break
    if (/[\w$>\-'"]/.test(nextChar)) {
      end++
    } else {
      break
    }
  }

  let word = content.substring(start, end).trim()
  word = word.replace(/^->+/, '').replace(/->+$/, '')
  return word
}

export function createWrapLogStatement(
  rawTarget: string,
  language = 'PHP'
): string {
  const isJavaScript =
    language === 'JavaScript' ||
    language === 'TypeScript' ||
    language === 'Vue' ||
    language === 'JS' ||
    language === 'TS'
  const text = rawTarget.trim()

  if (isJavaScript) {
    if (!text) return `console.log('DEBUG:', variable);`
    const escaped = text.replace(/'/g, "\\'")
    return `console.log('${escaped}:', ${text});`
  }

  // PHP Wrap Log (var_dump)
  if (!text) {
    return `var_dump($variable);`
  }

  let varExpr = text
  // If bare identifier without $, prepend $ for PHP variable convenience
  if (
    !varExpr.startsWith('$') &&
    !varExpr.startsWith('"') &&
    !varExpr.startsWith("'") &&
    /^[a-zA-Z_]\w*/.test(varExpr)
  ) {
    varExpr = `$${varExpr}`
  }

  return `var_dump(${varExpr});`
}

export function insertWrapLogStatement(
  content: string,
  selStart: number,
  selEnd: number,
  language = 'PHP'
): { newContent: string; newCursor: number } {
  const targetWord = extractTargetWord(content, selStart, selEnd)
  const logStatement = createWrapLogStatement(targetWord, language)

  const lineEnd = content.indexOf('\n', selEnd)
  const targetInsertPos = lineEnd === -1 ? content.length : lineEnd
  const lineStart = content.lastIndexOf('\n', selStart) + 1
  const indent = (content.substring(lineStart, targetInsertPos).match(/^[\t ]*/) || [''])[0]

  const insertText = `\n${indent}${logStatement}`
  const newContent = content.substring(0, targetInsertPos) + insertText + content.substring(targetInsertPos)
  const newCursor = targetInsertPos + insertText.length
  return { newContent, newCursor }
}

