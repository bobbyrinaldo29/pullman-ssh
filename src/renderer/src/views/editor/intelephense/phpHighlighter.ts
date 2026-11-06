// Robust, single-pass syntax highlighter for PHP
// Never replaces inside strings, comments, or generated HTML tags

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;')
}

// Single-pass tokenizer regex
// Order of precedence:
// 1. PHP Tags: <?php, ?>
// 2. Comments: //..., #..., /*...*/
// 3. Strings: "...", '...'
// 4. Variables: $varName
// 5. Keywords: class, function, if, return, etc.
// 6. Functions: functionName(
// 7. Numbers: 123, 45.67
// 8. Other / Plain characters
const TOKEN_REGEX =
  /(<\?php|\?>)|(\/\/[^\n]*|#[^\n]*|\/\*[\s\S]*?\*\/)|("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')|(\$[a-zA-Z_\x7f-\xff][a-zA-Z0-9_\x7f-\xff]*)|(\b(?:abstract|and|as|break|callable|case|catch|class|clone|const|continue|declare|default|die|do|echo|else|elseif|empty|enddeclare|endfor|endforeach|endif|endswitch|endwhile|enum|eval|exit|extends|final|finally|fn|for|foreach|function|global|goto|if|implements|include|include_once|instanceof|insteadof|interface|isset|list|match|namespace|new|or|print|private|protected|public|readonly|require|require_once|return|static|switch|throw|trait|try|unset|use|var|while|xor|yield)\b)|(\b[a-zA-Z_\x7f-\xff][a-zA-Z0-9_\x7f-\xff]*(?=\s*\())|(\b\d+(?:\.\d+)?\b)|([\s\S])/g

export function highlightPhpCode(rawCode: string): string {
  if (!rawCode) return ''

  let result = ''
  let match: RegExpExecArray | null

  TOKEN_REGEX.lastIndex = 0

  while ((match = TOKEN_REGEX.exec(rawCode)) !== null) {
    const [
      full,
      tagMatch,
      commentMatch,
      stringMatch,
      variableMatch,
      keywordMatch,
      functionMatch,
      numberMatch,
      plainMatch
    ] = match

    if (tagMatch) {
      result += `<span class="text-[#E5C07B] font-bold">${escapeHtml(tagMatch)}</span>`
    } else if (commentMatch) {
      result += `<span class="text-[#6A737D] italic">${escapeHtml(commentMatch)}</span>`
    } else if (stringMatch) {
      result += `<span class="text-[#98C379]">${escapeHtml(stringMatch)}</span>`
    } else if (variableMatch) {
      result += `<span class="text-[#E06C75]">${escapeHtml(variableMatch)}</span>`
    } else if (keywordMatch) {
      result += `<span class="text-[#C678DD] font-medium">${escapeHtml(keywordMatch)}</span>`
    } else if (functionMatch) {
      result += `<span class="text-[#61AFEF]">${escapeHtml(functionMatch)}</span>`
    } else if (numberMatch) {
      result += `<span class="text-[#D19A66]">${escapeHtml(numberMatch)}</span>`
    } else if (plainMatch) {
      result += escapeHtml(plainMatch)
    } else {
      result += escapeHtml(full)
    }
  }

  // Ensure trailing newline is rendered with height in <pre>
  if (rawCode.endsWith('\n')) {
    result += ' '
  }

  return result
}
