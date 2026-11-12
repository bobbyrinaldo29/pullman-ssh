/**
 * Parses unified diff string (e.g. from `git diff` or `git show`)
 * into original (left) and modified (right) text representations
 * for Monaco Diff Editor.
 */
export function parseUnifiedDiff(diff: string): { original: string; modified: string } {
  if (!diff || !diff.trim()) {
    return { original: '', modified: '' }
  }

  const origLines: string[] = []
  const modLines: string[] = []
  let inHunk = false

  for (const rawLine of diff.split('\n')) {
    if (rawLine.startsWith('@@')) {
      inHunk = true
      continue
    }
    if (!inHunk) continue

    if (rawLine.startsWith('+')) {
      modLines.push(rawLine.slice(1))
    } else if (rawLine.startsWith('-')) {
      origLines.push(rawLine.slice(1))
    } else if (rawLine.startsWith(' ') || rawLine === '') {
      const content = rawLine.startsWith(' ') ? rawLine.slice(1) : ''
      origLines.push(content)
      modLines.push(content)
    }
  }

  return {
    original: origLines.join('\n'),
    modified: modLines.join('\n')
  }
}

