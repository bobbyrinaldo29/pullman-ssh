/**
 * VS Code-style text editing commands:
 * - Duplicate line (Shift+Alt+Down / Shift+Alt+Up)
 * - Move line (Alt+Up / Alt+Down)
 * - Delete line (Cmd+Shift+K / Ctrl+Shift+K)
 * - Toggle line comment (Cmd+/ / Ctrl+/)
 */

export interface CommandResult {
  newContent: string
  newStart: number
  newEnd: number
}

export function moveLine(
  content: string,
  selStart: number,
  selEnd: number,
  direction: 'up' | 'down'
): CommandResult | null {
  const firstLineStart = content.lastIndexOf('\n', selStart - 1) + 1
  const lineEndIdx = content.indexOf('\n', selEnd)
  const lastLineEnd = lineEndIdx === -1 ? content.length : lineEndIdx

  const block = content.substring(firstLineStart, lastLineEnd)

  if (direction === 'up') {
    if (firstLineStart === 0) return null // Already at the top
    const prevLineStart = content.lastIndexOf('\n', firstLineStart - 2) + 1
    const prevLine = content.substring(prevLineStart, firstLineStart - 1)

    const before = content.substring(0, prevLineStart)
    const after = content.substring(lastLineEnd)
    const newContent = `${before}${block}\n${prevLine}${after}`

    const offsetStart = selStart - firstLineStart
    const offsetEnd = selEnd - firstLineStart

    return {
      newContent,
      newStart: prevLineStart + offsetStart,
      newEnd: prevLineStart + offsetEnd
    }
  } else {
    if (lastLineEnd === content.length) return null // Already at the bottom
    const nextLineEndIdx = content.indexOf('\n', lastLineEnd + 1)
    const nextLineEnd = nextLineEndIdx === -1 ? content.length : nextLineEndIdx
    const nextLine = content.substring(lastLineEnd + 1, nextLineEnd)

    const before = content.substring(0, firstLineStart)
    const after = content.substring(nextLineEnd)
    const newContent = `${before}${nextLine}\n${block}${after}`

    const offsetStart = selStart - firstLineStart
    const offsetEnd = selEnd - firstLineStart
    const targetStart = firstLineStart + nextLine.length + 1

    return {
      newContent,
      newStart: targetStart + offsetStart,
      newEnd: targetStart + offsetEnd
    }
  }
}

export function duplicateLine(
  content: string,
  selStart: number,
  selEnd: number,
  direction: 'up' | 'down' = 'down'
): CommandResult {
  const firstLineStart = content.lastIndexOf('\n', selStart - 1) + 1
  const lineEndIdx = content.indexOf('\n', selEnd)
  const lastLineEnd = lineEndIdx === -1 ? content.length : lineEndIdx

  const block = content.substring(firstLineStart, lastLineEnd)

  if (direction === 'down') {
    const before = content.substring(0, lastLineEnd)
    const after = content.substring(lastLineEnd)
    const newContent = `${before}\n${block}${after}`

    const shift = block.length + 1
    return {
      newContent,
      newStart: selStart + shift,
      newEnd: selEnd + shift
    }
  } else {
    const before = content.substring(0, firstLineStart)
    const after = content.substring(firstLineStart)
    const newContent = `${before}${block}\n${after}`

    return {
      newContent,
      newStart: selStart,
      newEnd: selEnd
    }
  }
}

export function deleteLine(
  content: string,
  selStart: number,
  selEnd: number
): CommandResult {
  const firstLineStart = content.lastIndexOf('\n', selStart - 1) + 1
  const lineEndIdx = content.indexOf('\n', selEnd)
  const lastLineEnd = lineEndIdx === -1 ? content.length : lineEndIdx

  let newContent = ''
  let newPos = firstLineStart

  if (lastLineEnd < content.length) {
    // Delete line including its trailing \n
    newContent = content.substring(0, firstLineStart) + content.substring(lastLineEnd + 1)
  } else if (firstLineStart > 0) {
    // Last line in file: delete including preceding \n
    newContent = content.substring(0, firstLineStart - 1)
    newPos = firstLineStart - 1
  } else {
    // Entire file
    newContent = ''
    newPos = 0
  }

  return {
    newContent,
    newStart: Math.min(newPos, newContent.length),
    newEnd: Math.min(newPos, newContent.length)
  }
}

export function toggleLineComment(
  content: string,
  selStart: number,
  selEnd: number,
  language = 'PHP'
): CommandResult {
  const prefix = language === 'Python' || language === 'Shell Script' ? '# ' : '// '
  const commentSymbol = prefix.trim()

  const firstLineStart = content.lastIndexOf('\n', selStart - 1) + 1
  const lineEndIdx = content.indexOf('\n', selEnd)
  const lastLineEnd = lineEndIdx === -1 ? content.length : lineEndIdx

  const lines = content.substring(firstLineStart, lastLineEnd).split('\n')
  const nonEmpty = lines.filter((l) => l.trim().length > 0)

  const isAllCommented =
    nonEmpty.length > 0 &&
    nonEmpty.every((l) => l.trimStart().startsWith(commentSymbol))

  const newLines = lines.map((line) => {
    if (!line.trim()) return line
    if (isAllCommented) {
      // Remove comment prefix
      const match = line.match(new RegExp(`^(\\s*)${commentSymbol}\\s?`))
      if (match) {
        return match[1] + line.slice(match[0].length)
      }
      return line
    } else {
      // Add comment prefix preserving indentation
      const match = line.match(/^(\s*)/)
      const indent = match ? match[1] : ''
      return `${indent}${prefix}${line.slice(indent.length)}`
    }
  })

  const transformed = newLines.join('\n')
  const before = content.substring(0, firstLineStart)
  const after = content.substring(lastLineEnd)
  const newContent = `${before}${transformed}${after}`

  return {
    newContent,
    newStart: firstLineStart,
    newEnd: firstLineStart + transformed.length
  }
}

