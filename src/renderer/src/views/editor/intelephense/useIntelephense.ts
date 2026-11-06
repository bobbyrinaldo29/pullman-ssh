import { ref, computed } from 'vue'
import {
  PhpSuggestion,
  PHP_KEYWORDS,
  PHP_SUPERGLOBALS,
  PHP_SNIPPETS,
  PHP_FUNCTIONS
} from './phpDictionary'

const ALL_PHP_ITEMS: PhpSuggestion[] = [
  ...PHP_SNIPPETS,
  ...PHP_SUPERGLOBALS,
  ...PHP_FUNCTIONS,
  ...PHP_KEYWORDS
]

export function useIntelephense() {
  const isOpen = ref(false)
  const query = ref('')
  const suggestions = ref<PhpSuggestion[]>([])
  const selectedIndex = ref(0)
  const popupCoords = ref({ top: 0, left: 0 })
  const replaceStart = ref(0)
  const replaceEnd = ref(0)
  const syntaxErrors = ref<string[]>([])

  const activeSuggestion = computed(() => {
    if (!isOpen.value || suggestions.value.length === 0) return null
    return suggestions.value[selectedIndex.value] || null
  })

  function checkSyntax(code: string, language: string): void {
    if (language !== 'PHP') {
      syntaxErrors.value = []
      return
    }

    const errors: string[] = []
    const stack: { char: string; line: number }[] = []
    const lines = code.split('\n')

    let inString: string | null = null
    let inComment = false

    lines.forEach((lineText, lineIdx) => {
      const lineNum = lineIdx + 1

      for (let i = 0; i < lineText.length; i++) {
        const ch = lineText[i]
        const next = lineText[i + 1]

        if (!inString && !inComment && ch === '/' && next === '/') {
          break // line comment
        }
        if (!inString && !inComment && ch === '/' && next === '*') {
          inComment = true
          i++
          continue
        }
        if (inComment && ch === '*' && next === '/') {
          inComment = false
          i++
          continue
        }
        if (inComment) continue

        if (!inString && (ch === '"' || ch === "'")) {
          inString = ch
          continue
        }
        if (inString && ch === inString && lineText[i - 1] !== '\\') {
          inString = null
          continue
        }
        if (inString) continue

        // Check brackets
        if (ch === '(' || ch === '[' || ch === '{') {
          stack.push({ char: ch, line: lineNum })
        } else if (ch === ')' || ch === ']' || ch === '}') {
          const expected = ch === ')' ? '(' : ch === ']' ? '[' : '{'
          if (stack.length === 0 || stack[stack.length - 1].char !== expected) {
            errors.push(`Unmatched '${ch}' at line ${lineNum}`)
          } else {
            stack.pop()
          }
        }
      }
    })

    if (stack.length > 0) {
      const unclosed = stack.pop()
      errors.push(`Unclosed '${unclosed?.char}' at line ${unclosed?.line}`)
    }

    syntaxErrors.value = errors
  }

  function triggerCompletion(
    textarea: HTMLTextAreaElement,
    code: string,
    language: string
  ): boolean {
    if (language !== 'PHP') {
      close()
      return false
    }

    const cursor = textarea.selectionStart
    const textBefore = code.substring(0, cursor)

    // Match word or variable prefix right before cursor
    const match = textBefore.match(/(\$[a-zA-Z0-9_]*|[a-zA-Z0-9_]{1,}|<\?php?)$/)
    if (!match) {
      close()
      return false
    }

    const word = match[1]
    query.value = word
    replaceStart.value = cursor - word.length
    replaceEnd.value = cursor

    const lowerWord = word.toLowerCase()
    const matches = ALL_PHP_ITEMS.filter((item) =>
      item.label.toLowerCase().startsWith(lowerWord) ||
      (lowerWord.length >= 2 && item.label.toLowerCase().includes(lowerWord))
    ).slice(0, 30)

    if (matches.length === 0) {
      close()
      return false
    }

    suggestions.value = matches
    selectedIndex.value = 0

    // Calculate approximate position of the cursor
    const lines = textBefore.split('\n')
    const currentLineIndex = lines.length - 1
    const currentLineText = lines[currentLineIndex]
    const lineHeight = 22
    const charWidth = 7.8

    const top = (currentLineIndex + 1) * lineHeight - textarea.scrollTop + 14
    const left = Math.min(
      Math.max(currentLineText.length * charWidth - textarea.scrollLeft + 12, 12),
      Math.max(textarea.clientWidth - 360, 12)
    )

    popupCoords.value = { top, left }
    isOpen.value = true
    return true
  }

  function selectNext(): void {
    if (!isOpen.value || suggestions.value.length === 0) return
    selectedIndex.value = (selectedIndex.value + 1) % suggestions.value.length
  }

  function selectPrev(): void {
    if (!isOpen.value || suggestions.value.length === 0) return
    selectedIndex.value =
      (selectedIndex.value - 1 + suggestions.value.length) % suggestions.value.length
  }

  function applyCompletion(
    content: string
  ): { newContent: string; newCursor: number } | null {
    if (!activeSuggestion.value) return null

    const item = activeSuggestion.value
    const before = content.substring(0, replaceStart.value)
    const after = content.substring(replaceEnd.value)
    const insert = item.insertText

    const newContent = before + insert + after
    let newCursor = before.length + insert.length
    if (item.cursorOffset) {
      newCursor += item.cursorOffset
    }

    close()
    return { newContent, newCursor }
  }

  function close(): void {
    isOpen.value = false
    suggestions.value = []
    selectedIndex.value = 0
  }

  return {
    isOpen,
    query,
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
    close
  }
}
