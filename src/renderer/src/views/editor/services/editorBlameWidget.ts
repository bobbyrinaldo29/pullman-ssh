import { monaco } from '../monaco/monacoSetup'
import { GitBlameInfo } from '../types'

const escapeHtml = (s: string): string =>
  s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')

export function createGitBlameWidget(
  getEditor: () => monaco.editor.IStandaloneCodeEditor | null,
  getBlame: () => GitBlameInfo | null | undefined
) {
  const domNode = document.createElement('div')
  domNode.className = 'monaco-git-blame-inline'
  domNode.style.display = 'none'

  const contentWidget: monaco.editor.IContentWidget = {
    getId: () => 'pullman.editor.gitBlameWidget',
    getDomNode: () => domNode,
    getPosition: () => {
      const blame = getBlame()
      const editor = getEditor()
      if (!blame || !blame.author || !editor) return null
      const pos = editor.getPosition()
      const model = editor.getModel()
      if (!pos || !model) return null

      const lineContent = model.getLineContent(pos.lineNumber)
      if (!lineContent.trim()) return null

      const maxCol = model.getLineMaxColumn(pos.lineNumber)
      return {
        position: { lineNumber: pos.lineNumber, column: maxCol },
        preference: [monaco.editor.ContentWidgetPositionPreference.EXACT]
      }
    }
  }

  function update(): void {
    const editor = getEditor()
    if (!editor) return
    const blame = getBlame()
    const pos = editor.getPosition()
    const model = editor.getModel()
    if (!blame?.author || !pos || !model || !model.getLineContent(pos.lineNumber).trim()) {
      domNode.style.display = 'none'
      domNode.innerHTML = ''
      editor.layoutContentWidget(contentWidget)
      return
    }

    const isCleanCommit = Boolean(
      blame.hash && !blame.isUncommitted && !blame.hash.startsWith('0000000') && blame.hash !== 'dirty'
    )
    const displayHash = isCleanCommit ? (blame.hash || '').substring(0, 7) : 'Uncommitted'

    domNode.style.display = 'inline-flex'
    domNode.innerHTML = `<div class="git-blame-badge" title="GitLens Blame: ${escapeHtml(blame.author)}, ${escapeHtml(blame.timeAgo || '')}"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="git-blame-icon"><circle cx="12" cy="12" r="3"></circle><line x1="3" y1="12" x2="9" y2="12"></line><line x1="15" y1="12" x2="21" y2="12"></line></svg><span class="git-blame-author">${escapeHtml(blame.author)}</span><span class="git-blame-time">${escapeHtml(blame.timeAgo || '')}</span><span class="git-blame-sep">•</span><span class="git-blame-summary">${escapeHtml(blame.summary || '')}</span></div><div class="git-blame-popover"><div class="git-blame-popover-header"><div class="git-blame-popover-hash"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:12px;height:12px;color:#38bdf8;"><circle cx="12" cy="12" r="3"></circle><line x1="3" y1="12" x2="9" y2="12"></line><line x1="15" y1="12" x2="21" y2="12"></line></svg><span>${displayHash}</span></div><div class="git-blame-popover-actions">${isCleanCommit ? `<button type="button" class="git-blame-action-btn" data-blame-action="copy">Copy SHA</button>` : ''}<button type="button" class="git-blame-action-btn git-blame-action-graph" data-blame-action="graph">Git Graph</button></div></div><div class="git-blame-popover-body"><div class="git-blame-popover-author"><strong>${escapeHtml(blame.author)}</strong> <span style="color:#64748b;">committed ${escapeHtml(blame.timeAgo || '')}</span></div><div class="git-blame-popover-msg">${escapeHtml(blame.summary || '')}</div></div></div>`

    editor.layoutContentWidget(contentWidget)
  }

  return {
    domNode,
    contentWidget,
    update
  }
}

