import type { RedmineAttachment, RedmineIssue, RedmineJournalDetail } from '../types'

export interface TextBlockPart {
  type: 'text' | 'image'
  text?: string
  filename?: string
  url?: string
  attachment?: RedmineAttachment
}

export interface PendingImageRef {
  name: string
  previewUrl?: string
}

export interface JournalFormatMaps {
  users: Map<number, string>
  statuses: Map<number, string>
  priorities: Map<number, string>
  customFields: Map<string, string>
}

/**
 * Formats an issue title with tracker and ID (e.g. "Bug Fix #144740 <subject>").
 */
export function formatIssueCopyTitle(
  issue: Pick<RedmineIssue, 'id' | 'subject'> & { tracker?: { name?: string } }
): string {
  const tracker = issue.tracker?.name?.trim()
  const prefix = tracker ? `${tracker} #${issue.id}` : `#${issue.id}`
  return `${prefix} ${issue.subject || ''}`.trim()
}

/**
 * Copies text to clipboard using Clipboard API with a hidden textarea fallback.
 */
export async function copyToClipboard(text: string): Promise<boolean> {
  if (!text) return false
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text)
      return true
    }
  } catch {
    // Fall back to execCommand below
  }

  try {
    const el = document.createElement('textarea')
    el.value = text
    el.setAttribute('readonly', '')
    el.style.position = 'fixed'
    el.style.left = '-9999px'
    document.body.appendChild(el)
    el.select()
    const copied = document.execCommand('copy')
    document.body.removeChild(el)
    return copied
  } catch {
    return false
  }
}

export function formatDate(dateStr?: string): string {
  if (!dateStr) return '-'
  const parts = dateStr.split('T')[0].split('-')
  return parts.length === 3 ? `${parts[2]}/${parts[1]}/${parts[0]}` : dateStr
}

export function formatRelative(dateStr?: string): string {
  if (!dateStr) return '-'
  const mins = Math.floor((Date.now() - new Date(dateStr).getTime()) / 60000)
  if (mins < 1) return 'less than a minute ago'
  if (mins < 60) return `${mins} minute${mins > 1 ? 's' : ''} ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `about ${hours} hour${hours > 1 ? 's' : ''} ago`
  const days = Math.floor(hours / 24)
  if (days < 30) return `${days} day${days > 1 ? 's' : ''} ago`
  return new Date(dateStr).toLocaleDateString()
}

export function formatShortRelative(dateStr: string): string {
  try {
    const diff = Date.now() - new Date(dateStr).getTime()
    const hours = Math.floor(diff / 3600000)
    if (hours < 1) return 'Just now'
    if (hours < 24) return `${hours}h ago`
    const days = Math.floor(hours / 24)
    if (days < 30) return `${days}d ago`
    return new Date(dateStr).toLocaleDateString()
  } catch {
    return dateStr
  }
}

export function formatJournalDate(dateStr?: string): string {
  if (!dateStr) return '-'
  const d = new Date(dateStr)
  if (isNaN(d.getTime())) return dateStr
  const day = String(d.getDate()).padStart(2, '0')
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
  const month = months[d.getMonth()]
  const year = d.getFullYear()
  const hours = String(d.getHours()).padStart(2, '0')
  const minutes = String(d.getMinutes()).padStart(2, '0')
  return `${day} ${month} ${year} ${hours}:${minutes}`
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function formatCustomValue(val: unknown): string {
  if (val === null || val === undefined || val === '') return '-'
  if (Array.isArray(val)) return val.length ? val.join(', ') : '-'
  return String(val)
}

export function isImageFile(filename: string): boolean {
  return /\.(png|jpe?g|gif|webp|svg|bmp)$/i.test(filename)
}

const WIKI_IMAGE_REGEX = /!(?:\{.*?\})?(?:<|>|=)?([^\s!]+?\.(?:png|jpe?g|gif|webp|svg|bmp))(?:\([^)]*?\))?!/gi

export function findWikiImageNames(text?: string): string[] {
  if (!text) return []
  const regex = new RegExp(WIKI_IMAGE_REGEX.source, 'gi')
  const list: string[] = []
  let m: RegExpExecArray | null
  while ((m = regex.exec(text)) !== null) {
    list.push(m[1].trim())
  }
  return list
}

function matchAttachmentByName<T extends { filename?: string; name?: string }>(
  list: T[],
  rawFilename: string
): T | undefined {
  const target = rawFilename.toLowerCase()
  return list.find((item) => {
    const candidate = (item.filename ?? item.name ?? '').toLowerCase()
    return candidate === target || target.endsWith(candidate)
  })
}

export function parseWikiContent(
  rawText?: string,
  attachments: RedmineAttachment[] = [],
  pendingFiles: PendingImageRef[] = []
): TextBlockPart[] {
  if (!rawText) return []

  const imgRegex = new RegExp(WIKI_IMAGE_REGEX.source, 'gi')
  const parts: TextBlockPart[] = []
  let lastIndex = 0
  let match: RegExpExecArray | null

  while ((match = imgRegex.exec(rawText)) !== null) {
    const matchIndex = match.index
    if (matchIndex > lastIndex) {
      parts.push({
        type: 'text',
        text: rawText.substring(lastIndex, matchIndex)
      })
    }

    const rawFilenameOrUrl = match[1].trim()
    const isHttp = rawFilenameOrUrl.startsWith('http://') || rawFilenameOrUrl.startsWith('https://')
    const matchedPending = matchAttachmentByName(pendingFiles, rawFilenameOrUrl)
    const matchedAtt = matchAttachmentByName(attachments, rawFilenameOrUrl)

    if (matchedPending) {
      parts.push({
        type: 'image',
        filename: matchedPending.name,
        url: matchedPending.previewUrl || ''
      })
    } else if (matchedAtt) {
      parts.push({
        type: 'image',
        filename: matchedAtt.filename,
        attachment: matchedAtt,
        url: matchedAtt.content_url
      })
    } else if (isHttp) {
      parts.push({
        type: 'image',
        filename: rawFilenameOrUrl.split('/').pop() || 'image',
        url: rawFilenameOrUrl
      })
    } else {
      parts.push({
        type: 'image',
        filename: rawFilenameOrUrl,
        url: ''
      })
    }

    lastIndex = matchIndex + match[0].length
  }

  if (lastIndex < rawText.length) {
    parts.push({
      type: 'text',
      text: rawText.substring(lastIndex)
    })
  }

  return parts
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function formatMappedChange(
  label: string,
  oldValue: string | undefined,
  newValue: string | undefined,
  lookup: (id: string) => string,
  newColorClass: string,
  allowClear = false
): { label: string; html: string } {
  const oldText = oldValue ? escapeHtml(lookup(oldValue)) : ''
  const newText = newValue ? escapeHtml(lookup(newValue)) : ''

  if (oldText && newText) {
    return {
      label,
      html: `${escapeHtml(label)} diubah dari <span class="text-slate-300 font-medium">${oldText}</span> menjadi <span class="${newColorClass}">${newText}</span>`
    }
  }
  if (newText || !allowClear) {
    return {
      label,
      html: `${escapeHtml(label)} diisi <span class="${newColorClass}">${newText || '-'}</span>`
    }
  }
  return {
    label,
    html: `${escapeHtml(label)} dihapus (sebelumnya <span class="text-slate-400">${oldText}</span>)`
  }
}

export function formatJournalDetail(
  d: RedmineJournalDetail,
  maps: JournalFormatMaps
): { label: string; html: string } {
  const prop = d.property || 'attr'
  const name = d.name

  if (name === 'status_id') {
    return formatMappedChange(
      'Status',
      d.old_value,
      d.new_value,
      (v) => maps.statuses.get(Number(v)) || v,
      'text-sky-300 font-bold'
    )
  }

  if (name === 'assigned_to_id') {
    return formatMappedChange(
      'Assignee',
      d.old_value,
      d.new_value,
      (v) => maps.users.get(Number(v)) || v,
      'text-sky-300 font-bold',
      true
    )
  }

  if (name === 'priority_id') {
    return formatMappedChange(
      'Prioritas',
      d.old_value,
      d.new_value,
      (v) => maps.priorities.get(Number(v)) || v,
      'text-amber-300 font-bold'
    )
  }

  if (name === 'done_ratio') {
    return {
      label: 'Done %',
      html: `Done % diubah dari <span class="text-slate-300 font-mono font-medium">${escapeHtml(d.old_value || '0')}</span> menjadi <span class="text-emerald-300 font-mono font-bold">${escapeHtml(d.new_value || '0')}</span>`
    }
  }

  if (name === 'estimated_hours') {
    return formatMappedChange('Estimated time', d.old_value, d.new_value, (v) => v, 'text-sky-300 font-bold')
  }

  if (name === 'due_date') {
    return formatMappedChange('Due date', d.old_value, d.new_value, (v) => v, 'text-sky-300 font-bold')
  }

  if (name === 'start_date') {
    return formatMappedChange('Start date', d.old_value, d.new_value, (v) => v, 'text-sky-300 font-bold')
  }

  if (name === 'description') {
    return {
      label: 'Deskripsi',
      html: d.old_value ? 'Deskripsi diperbarui' : 'Deskripsi diisi'
    }
  }

  const isFileName = (val?: string): boolean =>
    Boolean(val && /\.(png|jpe?g|gif|webp|svg|bmp|pdf|docx?|xlsx?|zip|rar|tar|gz|txt)$/i.test(val.trim()))

  if (prop === 'attachment' || isFileName(d.new_value) || isFileName(d.name)) {
    const file = escapeHtml(d.new_value || d.name)
    return {
      label: 'File',
      html: `File ditambahkan: <span class="text-emerald-300 font-medium font-mono">${file}</span>`
    }
  }

  if (prop === 'cf' || /^\d+$/.test(name)) {
    const cfName = maps.customFields.get(String(name)) || (name === '8' ? 'Poin' : `Custom Field #${name}`)
    return formatMappedChange(cfName, d.old_value, d.new_value, (v) => v, 'text-sky-300 font-bold')
  }

  if (prop === 'relation' || name === 'relates') {
    return {
      label: 'Relasi',
      html: `Relasi ${escapeHtml(d.name || 'relates')}: <span class="text-sky-300 font-mono font-bold">#${escapeHtml(d.new_value || '')}</span>`
    }
  }

  const label = escapeHtml(name.replace(/_/g, ' '))
  if (d.old_value && d.new_value) {
    return {
      label,
      html: `${label} diubah dari <span class="line-through text-slate-500">${escapeHtml(d.old_value)}</span> menjadi <span class="text-sky-300 font-medium">${escapeHtml(d.new_value)}</span>`
    }
  }
  return {
    label,
    html: `${label} diisi <span class="text-sky-300 font-medium">${escapeHtml(d.new_value || '-')}</span>`
  }
}

export const TOOLBAR_SNIPPETS: Record<string, { before: string; after?: string; placeholder: string }> = {
  bold: { before: '**', after: '**', placeholder: 'Bold text' },
  italic: { before: '_', after: '_', placeholder: 'Italic text' },
  underline: { before: '+', after: '+', placeholder: 'Underlined text' },
  strike: { before: '-', after: '-', placeholder: 'Deleted text' },
  code: { before: '@', after: '@', placeholder: 'code' },
  h1: { before: '\nh1. ', placeholder: 'Heading 1' },
  h2: { before: '\nh2. ', placeholder: 'Heading 2' },
  h3: { before: '\nh3. ', placeholder: 'Heading 3' },
  ul: { before: '\n* ', placeholder: 'Bullet item' },
  ol: { before: '\n# ', placeholder: 'Numbered item' },
  indent: { before: '\n> ', placeholder: 'Quoted text' },
  outdent: { before: '\n', placeholder: '' },
  pre: { before: '\n<pre>\n', after: '\n</pre>\n', placeholder: 'Preformatted block' },
  'code-block': { before: '\n<pre><code class="sql">\n', after: '\n</code></pre>\n', placeholder: '-- Code here' },
  link: { before: '"', after: '":https://example.com', placeholder: 'Link title' },
  image: { before: '!', after: '!', placeholder: 'https://example.com/image.png' },
  help: {
    before: '\n\n*Formatting:* **bold**, _italic_, +underline+, -strike-, @inline code@, h1. Heading\n',
    placeholder: ''
  }
}

export function getTrackerClass(name: string): string {
  const n = (name || '').toLowerCase()
  if (n.includes('bug') || n.includes('defect') || n.includes('error')) {
    return 'bg-rose-500/20 text-rose-300 border-rose-500/40 shadow-xs'
  }
  if (n.includes('feature') || n.includes('fitur')) {
    return 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40 shadow-xs'
  }
  if (n.includes('enhancement') || n.includes('enhance') || n.includes('peningkatan')) {
    return 'bg-purple-500/20 text-purple-300 border-purple-500/40 shadow-xs'
  }
  if (n.includes('task') || n.includes('tugas')) {
    return 'bg-sky-500/20 text-sky-300 border-sky-500/40 shadow-xs'
  }
  if (n.includes('support') || n.includes('bantuan')) {
    return 'bg-amber-500/20 text-amber-300 border-amber-500/40 shadow-xs'
  }
  return 'bg-indigo-500/20 text-indigo-300 border-indigo-500/40'
}

export function getStatusClass(name: string): string {
  const n = (name || '').toLowerCase().replace(/[-_]/g, ' ')
  if (n.includes('deployed') || n.includes('live') || n.includes('rilis')) {
    return 'bg-teal-500/20 text-teal-300 border-teal-500/40 font-medium'
  }
  if (n.includes('passed') || n.includes('pass') || n.includes('verified') || n.includes('approved')) {
    return 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40 font-medium'
  }
  if (n.includes('testing') || n.includes('qa') || n.includes('uji')) {
    return 'bg-violet-500/20 text-violet-300 border-violet-500/40 font-medium'
  }
  if (n.includes('ready') || n.includes('siap')) {
    return 'bg-cyan-500/20 text-cyan-300 border-cyan-500/40 font-medium'
  }
  if (n.includes('progress') || n.includes('working') || n.includes('sedang')) {
    return 'bg-amber-500/20 text-amber-300 border-amber-500/40 font-medium'
  }
  if (n.includes('new') || n.includes('baru') || n.includes('open')) {
    return 'bg-blue-500/20 text-blue-300 border-blue-500/40 font-medium'
  }
  if (n.includes('feedback') || n.includes('info') || n.includes('clarif')) {
    return 'bg-fuchsia-500/20 text-fuchsia-300 border-fuchsia-500/40 font-medium'
  }
  if (n.includes('resolved') || n.includes('solved')) {
    return 'bg-green-500/20 text-green-300 border-green-500/40 font-medium'
  }
  if (n.includes('closed') || n.includes('done') || n.includes('finish')) {
    return 'bg-slate-700/50 text-slate-300 border-slate-600/50'
  }
  if (n.includes('reject') || n.includes('cancel') || n.includes('batal') || n.includes('tolak')) {
    return 'bg-rose-500/20 text-rose-300 border-rose-500/40 font-medium'
  }
  if (n.includes('reopen')) {
    return 'bg-orange-500/20 text-orange-300 border-orange-500/40 font-medium'
  }
  return 'bg-slate-600/25 text-slate-300 border-slate-500/30'
}

export function getPriorityClass(name: string): string {
  const n = name.toLowerCase()
  if (n.includes('low')) return 'text-slate-400'
  if (n.includes('normal')) return 'text-slate-200'
  if (n.includes('high')) return 'text-amber-400 font-semibold'
  if (n.includes('urgent')) return 'text-orange-400 font-bold'
  if (n.includes('immediate')) return 'text-rose-400 font-bold'
  return 'text-slate-300'
}
