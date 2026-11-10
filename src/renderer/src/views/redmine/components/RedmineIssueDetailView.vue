<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import {
  Pencil,
  Clock,
  Star,
  Trash2,
  Quote,
  RotateCw,
  X,
  FileText,
  Download,
  Paperclip,
  ZoomIn
} from 'lucide-vue-next'
import { RedmineIssue, RedmineStatus, RedminePriority, RedmineConfig, RedmineUploadItem, RedmineAttachment } from '../types'
import RedmineIssueEditForm from './RedmineIssueEditForm.vue'

const props = defineProps<{
  issue: RedmineIssue
  statuses: RedmineStatus[]
  priorities: RedminePriority[]
  isLoading: boolean
  users?: Array<{ id: number; name: string }>
  config?: RedmineConfig
  uploadAttachment?: (file: File) => Promise<{ success: boolean; token?: string; error?: string }>
  loadAttachmentDataUrl?: (contentUrl: string) => Promise<string | null>
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'back-to-issues'): void
  (e: 'update-issue', payload: {
    id: number
    status_id?: number
    priority_id?: number
    assigned_to_id?: number
    done_ratio?: number
    notes?: string
    uploads?: RedmineUploadItem[]
  }): void
  (e: 'refresh', issueId: number): void
}>()

const showEditForm = ref(false)
const isWatching = ref(false)
const editFormRef = ref<InstanceType<typeof RedmineIssueEditForm> | null>(null)
const editFormContainerRef = ref<HTMLElement | null>(null)
const lightboxImage = ref<{ url: string; title: string } | null>(null)

function formatDate(dateStr?: string): string {
  if (!dateStr) return '-'
  const parts = dateStr.split('T')[0].split('-')
  return parts.length === 3 ? `${parts[2]}/${parts[1]}/${parts[0]}` : dateStr
}

function formatRelative(dateStr?: string): string {
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

function formatJournalDate(dateStr?: string): string {
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

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function formatCustomValue(val: unknown): string {
  if (val === null || val === undefined || val === '') return '-'
  if (Array.isArray(val)) return val.length ? val.join(', ') : '-'
  return String(val)
}

function isImageFile(filename: string): boolean {
  return /\.(png|jpe?g|gif|webp|svg|bmp)$/i.test(filename)
}

function getAttachmentUrl(att: { content_url: string }): string {
  if (!att?.content_url) return ''
  const separator = att.content_url.includes('?') ? '&' : '?'
  const key = props.config?.apiKey ? `key=${encodeURIComponent(props.config.apiKey)}` : ''
  return key ? `${att.content_url}${separator}${key}` : att.content_url
}

// Reactive base64 cache for images to avoid CORS and authentication drops
const imageCache = ref<Record<string, string>>({})
const loadingImages = new Set<string>()

function triggerLoadImage(contentUrl?: string, filename?: string): void {
  if (!contentUrl || loadingImages.has(contentUrl) || !props.loadAttachmentDataUrl) return
  loadingImages.add(contentUrl)
  props
    .loadAttachmentDataUrl(contentUrl)
    .then((dataUrl) => {
      loadingImages.delete(contentUrl)
      if (dataUrl) {
        imageCache.value[contentUrl] = dataUrl
        if (filename) imageCache.value[filename] = dataUrl
      }
    })
    .catch(() => {
      loadingImages.delete(contentUrl)
    })
}

async function preloadImages(): Promise<void> {
  const attachments = props.issue.attachments || []

  // 1. Preload all attachments that are images
  for (const att of attachments) {
    if (!isImageFile(att.filename)) continue
    if (imageCache.value[att.filename] || imageCache.value[att.content_url]) continue
    if (props.loadAttachmentDataUrl && att.content_url) {
      try {
        const dataUrl = await props.loadAttachmentDataUrl(att.content_url)
        if (dataUrl) {
          imageCache.value[att.content_url] = dataUrl
          imageCache.value[att.filename] = dataUrl
          imageCache.value[String(att.id)] = dataUrl
        }
      } catch (err) {
        console.warn('Failed to load image data URL:', att.filename, err)
      }
    }
  }

  // 2. Preload any wiki images mentioned in description or journal notes
  const findWikiNames = (text?: string): string[] => {
    if (!text) return []
    const regex = /!(?:\{.*?\})?(?:<|>|=)?([^\s!]+?\.(?:png|jpe?g|gif|webp|svg|bmp))(?:\([^\)]*?\))?!/gi
    const list: string[] = []
    let m: RegExpExecArray | null
    while ((m = regex.exec(text)) !== null) {
      list.push(m[1].trim())
    }
    return list
  }

  const allNames = [
    ...findWikiNames(props.issue.description),
    ...(props.issue.journals || []).flatMap((j) => findWikiNames(j.notes))
  ]

  for (const name of allNames) {
    if (imageCache.value[name]) continue
    const matched = attachments.find(
      (a) => a.filename.toLowerCase() === name.toLowerCase() || name.toLowerCase().endsWith(a.filename.toLowerCase())
    )
    if (matched && matched.content_url && !imageCache.value[matched.content_url] && props.loadAttachmentDataUrl) {
      try {
        const dataUrl = await props.loadAttachmentDataUrl(matched.content_url)
        if (dataUrl) {
          imageCache.value[matched.content_url] = dataUrl
          imageCache.value[matched.filename] = dataUrl
          imageCache.value[name] = dataUrl
        }
      } catch (err) {
        console.warn('Failed to load wiki image:', name, err)
      }
    }
  }
}

watch(
  () => [props.issue.id, props.issue.attachments],
  () => {
    preloadImages()
  },
  { immediate: true, deep: true }
)

function getImageSrc(att?: { content_url?: string; filename?: string } | null, fallbackUrl?: string): string {
  if (att) {
    if (att.filename && imageCache.value[att.filename]) return imageCache.value[att.filename]
    if (att.content_url && imageCache.value[att.content_url]) return imageCache.value[att.content_url]
    if (att.content_url) {
      triggerLoadImage(att.content_url, att.filename)
      return getAttachmentUrl({ content_url: att.content_url })
    }
  }
  if (fallbackUrl) {
    if (imageCache.value[fallbackUrl]) return imageCache.value[fallbackUrl]
    const matched = (props.issue.attachments || []).find(
      (a) => a.filename.toLowerCase() === fallbackUrl.toLowerCase() || fallbackUrl.toLowerCase().endsWith(a.filename.toLowerCase())
    )
    if (matched) {
      if (imageCache.value[matched.filename]) return imageCache.value[matched.filename]
      if (imageCache.value[matched.content_url]) return imageCache.value[matched.content_url]
      if (matched.content_url) {
        triggerLoadImage(matched.content_url, matched.filename)
        return getAttachmentUrl(matched)
      }
    }
    return fallbackUrl
  }
  return ''
}

interface TextBlockPart {
  type: 'text' | 'image'
  text?: string
  filename?: string
  url?: string
  attachment?: RedmineAttachment
}

function parseWikiContent(rawText?: string): TextBlockPart[] {
  if (!rawText) return []
  const text = rawText
  const attachments = props.issue.attachments || []

  // Match Redmine image syntax: !filename.ext! or !{options}filename.ext! or !http...ext!
  const imgRegex = /!(?:\{.*?\})?(?:<|>|=)?([^\s!]+?\.(?:png|jpe?g|gif|webp|svg|bmp))(?:\([^\)]*?\))?!/gi
  const parts: TextBlockPart[] = []
  let lastIndex = 0
  let match: RegExpExecArray | null = null

  while ((match = imgRegex.exec(text)) !== null) {
    const matchIndex = match.index
    if (matchIndex > lastIndex) {
      parts.push({
        type: 'text',
        text: text.substring(lastIndex, matchIndex)
      })
    }

    const rawFilenameOrUrl = match[1].trim()
    const isHttp = rawFilenameOrUrl.startsWith('http://') || rawFilenameOrUrl.startsWith('https://')

    const matchedAtt = attachments.find(
      (a) =>
        a.filename.toLowerCase() === rawFilenameOrUrl.toLowerCase() ||
        rawFilenameOrUrl.toLowerCase().endsWith(a.filename.toLowerCase())
    )

    if (matchedAtt) {
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
        url: rawFilenameOrUrl
      })
    }

    lastIndex = matchIndex + match[0].length
  }

  if (lastIndex < text.length) {
    parts.push({
      type: 'text',
      text: text.substring(lastIndex)
    })
  }

  return parts
}

const parsedDescriptionParts = computed(() => parseWikiContent(props.issue.description))

const customFields = computed(() => props.issue.custom_fields || [])

const leftCustomFields = computed(() => {
  const fields = customFields.value
  const half = Math.ceil(fields.length / 2)
  return fields.slice(0, half)
})

const rightCustomFields = computed(() => {
  const fields = customFields.value
  const half = Math.ceil(fields.length / 2)
  return fields.slice(half)
})

// Build resolution maps for journal history IDs to human-readable names
const userMap = computed(() => {
  const map = new Map<number, string>()
  if (props.users) {
    for (const u of props.users) {
      if (u.id) map.set(u.id, u.name)
    }
  }
  if (props.issue.author) {
    map.set(props.issue.author.id, props.issue.author.name)
  }
  if (props.issue.assigned_to) {
    map.set(props.issue.assigned_to.id, props.issue.assigned_to.name)
  }
  if (props.issue.journals) {
    for (const j of props.issue.journals) {
      if (j.user?.id) {
        map.set(j.user.id, j.user.name)
      }
    }
  }
  return map
})

const statusMap = computed(() => {
  const map = new Map<number, string>()
  for (const s of props.statuses) {
    map.set(s.id, s.name)
  }
  return map
})

const priorityMap = computed(() => {
  const map = new Map<number, string>()
  for (const p of props.priorities) {
    map.set(p.id, p.name)
  }
  return map
})

const customFieldMap = computed(() => {
  const map = new Map<string, string>()
  if (props.issue.custom_fields) {
    for (const cf of props.issue.custom_fields) {
      map.set(String(cf.id), cf.name)
      map.set(cf.name.toLowerCase(), cf.name)
    }
  }
  return map
})

function formatJournalDetail(d: { property: string; name: string; old_value?: string; new_value?: string }): { label: string; html: string } {
  const prop = d.property || 'attr'
  const name = d.name

  // 1. Status
  if (name === 'status_id') {
    const oldName = d.old_value ? (statusMap.value.get(Number(d.old_value)) || d.old_value) : ''
    const newName = d.new_value ? (statusMap.value.get(Number(d.new_value)) || d.new_value) : ''
    if (oldName && newName) {
      return {
        label: 'Status',
        html: `Status diubah dari <span class="text-slate-300 font-medium">${oldName}</span> menjadi <span class="text-sky-300 font-bold">${newName}</span>`
      }
    }
    return {
      label: 'Status',
      html: `Status diisi <span class="text-sky-300 font-bold">${newName}</span>`
    }
  }

  // 2. Assignee
  if (name === 'assigned_to_id') {
    const oldName = d.old_value ? (userMap.value.get(Number(d.old_value)) || d.old_value) : ''
    const newName = d.new_value ? (userMap.value.get(Number(d.new_value)) || d.new_value) : ''
    if (oldName && newName) {
      return {
        label: 'Assignee',
        html: `Assignee diubah dari <span class="text-slate-300 font-medium">${oldName}</span> menjadi <span class="text-sky-300 font-bold">${newName}</span>`
      }
    }
    if (newName) {
      return {
        label: 'Assignee',
        html: `Assignee diisi <span class="text-sky-300 font-bold">${newName}</span>`
      }
    }
    return {
      label: 'Assignee',
      html: `Assignee dihapus (sebelumnya <span class="text-slate-400">${oldName}</span>)`
    }
  }

  // 3. Priority
  if (name === 'priority_id') {
    const oldName = d.old_value ? (priorityMap.value.get(Number(d.old_value)) || d.old_value) : ''
    const newName = d.new_value ? (priorityMap.value.get(Number(d.new_value)) || d.new_value) : ''
    if (oldName && newName) {
      return {
        label: 'Prioritas',
        html: `Prioritas diubah dari <span class="text-slate-300 font-medium">${oldName}</span> menjadi <span class="text-amber-300 font-bold">${newName}</span>`
      }
    }
    return {
      label: 'Prioritas',
      html: `Prioritas diisi <span class="text-amber-300 font-bold">${newName}</span>`
    }
  }

  // 4. Done Ratio (% Done)
  if (name === 'done_ratio') {
    return {
      label: 'Done %',
      html: `Done % diubah dari <span class="text-slate-300 font-mono font-medium">${d.old_value || 0}</span> menjadi <span class="text-emerald-300 font-mono font-bold">${d.new_value}</span>`
    }
  }

  // 5. Estimated Hours
  if (name === 'estimated_hours') {
    if (d.old_value) {
      return {
        label: 'Estimated time',
        html: `Estimated time diubah dari <span class="text-slate-300">${d.old_value}</span> menjadi <span class="text-sky-300 font-bold">${d.new_value}</span>`
      }
    }
    return {
      label: 'Estimated time',
      html: `Estimated time diisi <span class="text-sky-300 font-bold">${d.new_value}</span>`
    }
  }

  // 6. Due Date
  if (name === 'due_date') {
    if (d.old_value) {
      return {
        label: 'Due date',
        html: `Due date diubah dari <span class="text-slate-300">${d.old_value}</span> menjadi <span class="text-sky-300 font-bold">${d.new_value}</span>`
      }
    }
    return {
      label: 'Due date',
      html: `Due date diisi <span class="text-sky-300 font-bold">${d.new_value}</span>`
    }
  }

  // 7. Start Date
  if (name === 'start_date') {
    if (d.old_value) {
      return {
        label: 'Start date',
        html: `Start date diubah dari <span class="text-slate-300">${d.old_value}</span> menjadi <span class="text-sky-300 font-bold">${d.new_value}</span>`
      }
    }
    return {
      label: 'Start date',
      html: `Start date diisi <span class="text-sky-300 font-bold">${d.new_value}</span>`
    }
  }

  // 8. Description (Simplified format per user request: "deskripsi diubah jadi lebih sederhana aja")
  if (name === 'description') {
    return {
      label: 'Deskripsi',
      html: d.old_value ? 'Deskripsi diperbarui' : 'Deskripsi diisi'
    }
  }

  // 9. Files & Attachments (or custom fields containing filenames)
  const isFileName = (val?: string): boolean =>
    !!val && /\.(png|jpe?g|gif|webp|svg|bmp|pdf|docx?|xlsx?|zip|rar|tar|gz|txt)$/i.test(val.trim())

  if (prop === 'attachment' || isFileName(d.new_value) || isFileName(d.name)) {
    const file = d.new_value || d.name
    return {
      label: 'File',
      html: `File ditambahkan: <span class="text-emerald-300 font-medium font-mono">${file}</span>`
    }
  }

  // 10. Custom Field (property === 'cf' atau nama angka)
  if (prop === 'cf' || /^\d+$/.test(name)) {
    const cfName = customFieldMap.value.get(String(name)) || (name === '8' ? 'Poin' : `Custom Field #${name}`)
    if (d.old_value && d.new_value) {
      return {
        label: cfName,
        html: `${cfName} diubah dari <span class="text-slate-300">${d.old_value}</span> menjadi <span class="text-sky-300 font-bold">${d.new_value}</span>`
      }
    }
    return {
      label: cfName,
      html: `${cfName} diisi <span class="text-sky-300 font-bold">${d.new_value || '-'}</span>`
    }
  }

  // 11. Relation
  if (prop === 'relation' || name === 'relates') {
    return {
      label: 'Relasi',
      html: `Relasi ${d.name || 'relates'}: <span class="text-sky-300 font-mono font-bold">#${d.new_value}</span>`
    }
  }

  // Default fallback
  const label = name.replace(/_/g, ' ')
  if (d.old_value && d.new_value) {
    return {
      label,
      html: `${label} diubah dari <span class="line-through text-slate-500">${d.old_value}</span> menjadi <span class="text-sky-300 font-medium">${d.new_value}</span>`
    }
  }
  return {
    label,
    html: `${label} diisi <span class="text-sky-300 font-medium">${d.new_value}</span>`
  }
}

// Function to handle clicking Edit button (Requirement 4)
function handleOpenEdit(): void {
  showEditForm.value = true
  nextTick(() => {
    editFormContainerRef.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    editFormRef.value?.focus()
  })
}

function quoteDescription(): void {
  if (!props.issue.description) return
  handleOpenEdit()
  const quoteLines = props.issue.description.split('\n').map((l) => `> ${l}`).join('\n')
  editFormRef.value?.insertQuote(quoteLines)
}

function handleFormSubmit(payload: {
  status_id?: number
  priority_id?: number
  assigned_to_id?: number
  done_ratio?: number
  notes?: string
  uploads?: RedmineUploadItem[]
}): void {
  emit('update-issue', {
    id: props.issue.id,
    ...payload
  })
  showEditForm.value = false
}
</script>

<template>
  <div class="flex-1 flex flex-col bg-[#141822] text-slate-200 overflow-hidden font-sans select-text text-[12px] leading-normal">
    <!-- Top Bar with Refresh & Close Tab Shortcut -->
    <div class="px-6 py-2 bg-[#1b212e] border-b border-[#283244] flex items-center justify-between text-xs select-none shrink-0">
      <div class="flex items-center space-x-2 text-slate-400">
        <button
          type="button"
          class="text-sky-400 hover:text-sky-300 hover:underline cursor-pointer font-medium"
          @click="emit('back-to-issues')"
        >
          &laquo; Back to Issues
        </button>
        <span>&bull;</span>
        <span class="text-slate-200 font-semibold">{{ props.issue.project?.name }}</span>
      </div>
      <div class="flex items-center space-x-2">
        <button
          type="button"
          class="px-2.5 py-1 rounded text-[11px] text-slate-300 hover:text-white bg-[#222a3a] hover:bg-[#2b3548] border border-[#2e394d] transition-colors cursor-pointer flex items-center space-x-1"
          title="Refresh issue data"
          @click="emit('refresh', props.issue.id)"
        >
          <RotateCw class="w-3 h-3" :class="{ 'animate-spin': props.isLoading }" />
          <span>Refresh</span>
        </button>
        <button
          type="button"
          class="px-2.5 py-1 rounded text-[11px] text-rose-400 hover:text-white hover:bg-rose-600/20 border border-rose-500/30 transition-colors cursor-pointer flex items-center space-x-1"
          title="Close tab"
          @click="emit('close')"
        >
          <X class="w-3.5 h-3.5" />
          <span>Close</span>
        </button>
      </div>
    </div>

    <!-- Scrollable Main Content matching exact Redmine Web Ticket layout (Full Width) -->
    <div class="flex-1 overflow-y-auto px-6 py-4 space-y-4 w-full">
      <div class="w-full space-y-4">
        <!-- Top Row: Tracker #ID & Web Action Buttons -->
        <div class="flex items-center justify-between flex-wrap gap-2 select-none">
          <h2 class="text-xl font-bold text-white tracking-tight">
            {{ props.issue.tracker?.name }} #{{ props.issue.id }}
          </h2>

          <!-- Action Buttons Bar (Edit, Log time, Watch, Delete) -->
          <div class="flex items-center space-x-3 text-[11px]">
            <button
              type="button"
              class="flex items-center space-x-1 text-sky-400 hover:text-sky-300 hover:underline cursor-pointer font-medium"
              @click="handleOpenEdit"
            >
              <Pencil class="w-3.5 h-3.5 text-amber-400" />
              <span>Edit</span>
            </button>
            <button
              type="button"
              class="flex items-center space-x-1 text-sky-400 hover:text-sky-300 hover:underline cursor-pointer font-medium"
              @click="handleOpenEdit"
            >
              <Clock class="w-3.5 h-3.5 text-emerald-400" />
              <span>Log time</span>
            </button>
            <button
              type="button"
              class="flex items-center space-x-1 text-sky-400 hover:text-sky-300 hover:underline cursor-pointer font-medium"
              @click="isWatching = !isWatching"
            >
              <Star class="w-3.5 h-3.5" :class="isWatching ? 'text-amber-400 fill-amber-400' : 'text-slate-400'" />
              <span>{{ isWatching ? 'Unwatch' : 'Watch' }}</span>
            </button>
            <button
              type="button"
              class="flex items-center space-x-1 text-slate-400 hover:text-rose-400 hover:underline cursor-pointer font-medium"
              title="Close issue tab"
              @click="emit('close')"
            >
              <Trash2 class="w-3.5 h-3.5 text-slate-400" />
              <span>Delete</span>
            </button>
          </div>
        </div>

        <!-- Issue Details Box (Redmine Web Layout adapted to Dark Theme) -->
        <div class="bg-[#1b212e] border border-[#2b3548] rounded-md p-4 md:p-5 shadow-sm space-y-4">
          <!-- Subject & Meta info -->
          <div class="space-y-1">
            <div class="flex items-start justify-between gap-4">
              <h3 class="text-[14px] md:text-[15px] font-bold text-white leading-snug">
                {{ props.issue.subject }}
              </h3>
              <div class="text-[10px] text-slate-500 whitespace-nowrap select-none">
                <span>&laquo; Previous</span>
                <span class="mx-1.5">|</span>
                <span>1 of 1</span>
                <span class="mx-1.5">|</span>
                <span>Next &raquo;</span>
              </div>
            </div>

            <!-- Author & relative timestamps -->
            <div class="text-[11px] text-slate-400">
              <span>Added by </span>
              <span class="text-sky-400 hover:underline cursor-pointer font-semibold">{{ props.issue.author?.name }}</span>
              <span> {{ formatRelative(props.issue.created_on) }}.</span>
              <span v-if="props.issue.updated_on"> Updated <span class="text-sky-400 hover:underline cursor-pointer">{{ formatRelative(props.issue.updated_on) }}</span>.</span>
            </div>
          </div>

          <!-- 2-Column Attributes Grid (Classic Redmine Attributes Table) -->
          <div class="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-1 pt-2 text-[11px] leading-relaxed">
            <!-- Left Column -->
            <div class="space-y-0.5">
              <div class="grid grid-cols-[125px_1fr] py-0.5">
                <span class="font-bold text-slate-400">Status:</span>
                <span class="text-sky-300 font-semibold">{{ props.issue.status?.name }}</span>
              </div>
              <div class="grid grid-cols-[125px_1fr] py-0.5">
                <span class="font-bold text-slate-400">Priority:</span>
                <span class="text-amber-400 font-medium">{{ props.issue.priority?.name }}</span>
              </div>
              <div class="grid grid-cols-[125px_1fr] py-0.5">
                <span class="font-bold text-slate-400">Assignee:</span>
                <span class="text-sky-400 hover:underline cursor-pointer font-medium">
                  {{ props.issue.assigned_to?.name || '-' }}
                </span>
              </div>
              <div class="grid grid-cols-[125px_1fr] py-0.5">
                <span class="font-bold text-slate-400">Target version:</span>
                <span class="text-slate-500">-</span>
              </div>

              <!-- Dynamic Left Custom Fields -->
              <div
                v-for="cf in leftCustomFields"
                :key="cf.id"
                class="grid grid-cols-[125px_1fr] py-0.5"
              >
                <span class="font-bold text-slate-400 truncate pr-1" :title="cf.name">{{ cf.name }}:</span>
                <span class="text-slate-200">{{ formatCustomValue(cf.value) }}</span>
              </div>
            </div>

            <!-- Right Column -->
            <div class="space-y-0.5">
              <div class="grid grid-cols-[125px_1fr] py-0.5">
                <span class="font-bold text-slate-400">Start date:</span>
                <span class="text-slate-300">{{ formatDate(props.issue.start_date) }}</span>
              </div>
              <div class="grid grid-cols-[125px_1fr] py-0.5">
                <span class="font-bold text-slate-400">Due date:</span>
                <span class="text-slate-300">{{ formatDate(props.issue.due_date) }}</span>
              </div>
              <div class="grid grid-cols-[125px_1fr] py-0.5 items-center">
                <span class="font-bold text-slate-400">% Done:</span>
                <div class="flex items-center space-x-2">
                  <div class="w-24 h-2 bg-[#141822] rounded-full overflow-hidden border border-[#2b364a]">
                    <div
                      class="h-full rounded-full transition-all"
                      :class="props.issue.done_ratio === 100 ? 'bg-emerald-500' : 'bg-blue-500'"
                      :style="{ width: `${props.issue.done_ratio || 0}%` }"
                    ></div>
                  </div>
                  <span class="text-[11px] text-slate-400 font-mono">{{ props.issue.done_ratio || 0 }}%</span>
                </div>
              </div>
              <div class="grid grid-cols-[125px_1fr] py-0.5">
                <span class="font-bold text-slate-400">Estimated time:</span>
                <span class="text-slate-300">{{ props.issue.estimated_hours ? `${props.issue.estimated_hours.toFixed(2)} h` : '-' }}</span>
              </div>

              <!-- Dynamic Right Custom Fields -->
              <div
                v-for="cf in rightCustomFields"
                :key="cf.id"
                class="grid grid-cols-[125px_1fr] py-0.5"
              >
                <span class="font-bold text-slate-400 truncate pr-1" :title="cf.name">{{ cf.name }}:</span>
                <span class="text-slate-200">{{ formatCustomValue(cf.value) }}</span>
              </div>
            </div>
          </div>

          <!-- Divider -->
          <hr class="border-[#273245] my-2" />

          <!-- Description Section -->
          <div class="space-y-1.5 pt-1">
            <div class="flex items-center justify-between">
              <span class="font-bold text-slate-300 text-[12px]">Description</span>
              <button
                type="button"
                class="text-sky-400 hover:underline cursor-pointer text-[11px] flex items-center space-x-1"
                @click="quoteDescription"
              >
                <Quote class="w-3 h-3 text-slate-400" />
                <span>Quote</span>
              </button>
            </div>
            <div class="text-[12px] text-slate-200 bg-[#141822] border border-[#242e40] rounded p-4 leading-relaxed font-sans select-text space-y-2">
              <template v-if="parsedDescriptionParts.length > 0">
                <template v-for="(part, pIdx) in parsedDescriptionParts" :key="pIdx">
                  <!-- Text Part -->
                  <div v-if="part.type === 'text'" class="whitespace-pre-wrap leading-relaxed">
                    {{ part.text }}
                  </div>

                  <!-- Inline Wiki Image Part (Requirement 2 & User Request) -->
                  <div v-else-if="part.type === 'image'" class="my-3">
                    <div
                      class="inline-block max-w-full rounded-lg border border-[#2b3548] bg-[#0c1017] shadow-lg cursor-pointer group hover:border-sky-500/70 transition-all overflow-hidden"
                      @click="lightboxImage = { url: getImageSrc(part.attachment, part.url), title: part.filename || 'Image' }"
                    >
                      <div class="relative flex items-center justify-center bg-black/40 min-h-[60px] min-w-[140px]">
                        <img
                          :src="getImageSrc(part.attachment, part.url)"
                          :alt="part.filename"
                          class="max-w-full max-h-[650px] object-contain block group-hover:scale-[1.005] transition-transform"
                          loading="lazy"
                        />
                        <!-- Zoom badge on hover -->
                        <div class="absolute top-2 right-2 px-2 py-1 bg-black/75 rounded text-[10px] text-sky-300 opacity-0 group-hover:opacity-100 transition-opacity flex items-center space-x-1 shadow">
                          <ZoomIn class="w-3 h-3" />
                          <span>Click to zoom</span>
                        </div>
                      </div>
                      <div class="px-3 py-1.5 text-[11px] text-slate-400 bg-[#141924] border-t border-[#222a3a] flex items-center justify-between">
                        <span class="font-mono text-slate-300 truncate mr-3">{{ part.filename }}</span>
                        <span class="text-[10px] text-sky-400 flex items-center space-x-1 shrink-0">
                          <ZoomIn class="w-3 h-3" />
                          <span>View full size</span>
                        </span>
                      </div>
                    </div>
                  </div>
                </template>
              </template>
              <div v-else class="text-slate-500 italic">No description provided.</div>
            </div>
          </div>

          <!-- Attachments / Files Section with Direct Image Previews (Requirement 2) -->
          <div v-if="props.issue.attachments && props.issue.attachments.length > 0" class="space-y-2 pt-2 border-t border-[#273245]">
            <div class="flex items-center space-x-2 text-xs font-bold text-slate-300">
              <Paperclip class="w-3.5 h-3.5 text-sky-400" />
              <span>Files / Attachments ({{ props.issue.attachments.length }})</span>
            </div>

            <!-- Image Attachments Direct Grid Preview -->
            <div
              v-if="props.issue.attachments.some((a) => isImageFile(a.filename))"
              class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3 py-1"
            >
              <div
                v-for="att in props.issue.attachments.filter((a) => isImageFile(a.filename))"
                :key="att.id"
                class="group relative border border-[#2b364a] rounded-lg overflow-hidden bg-[#11151f] hover:border-sky-500/60 transition-all shadow-sm flex flex-col cursor-pointer"
                @click="lightboxImage = { url: getImageSrc(att), title: att.filename }"
              >
                <div class="w-full h-32 bg-black/50 overflow-hidden flex items-center justify-center relative">
                  <img
                    :src="getImageSrc(att)"
                    :alt="att.filename"
                    class="w-full h-full object-contain group-hover:scale-105 transition-transform duration-200"
                    loading="lazy"
                  />
                  <!-- Zoom overlay -->
                  <div class="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 flex items-center justify-center transition-opacity text-white">
                    <ZoomIn class="w-6 h-6 text-sky-300 drop-shadow" />
                  </div>
                </div>

                <div class="p-2 flex items-center justify-between text-[11px] bg-[#161b26] border-t border-[#242d3d]">
                  <div class="truncate mr-1">
                    <div class="font-medium text-slate-200 truncate" :title="att.filename">{{ att.filename }}</div>
                    <div class="text-[10px] text-slate-500 font-mono">{{ formatFileSize(att.filesize) }}</div>
                  </div>
                  <a
                    :href="getImageSrc(att)"
                    :download="att.filename"
                    target="_blank"
                    class="p-1 text-slate-400 hover:text-sky-300 hover:bg-[#202737] rounded transition-colors"
                    title="Download / Open file"
                    @click.stop
                  >
                    <Download class="w-3.5 h-3.5" />
                  </a>
                </div>
              </div>
            </div>

            <!-- Non-image Attachments List -->
            <div
              v-if="props.issue.attachments.some((a) => !isImageFile(a.filename))"
              class="space-y-1.5 pt-1"
            >
              <div
                v-for="att in props.issue.attachments.filter((a) => !isImageFile(a.filename))"
                :key="att.id"
                class="flex items-center justify-between px-3 py-1.5 rounded bg-[#141822] border border-[#242e40] text-xs hover:border-[#323f54] transition-colors"
              >
                <div class="flex items-center space-x-2 truncate">
                  <FileText class="w-4 h-4 text-sky-400 shrink-0" />
                  <a
                    :href="getAttachmentUrl(att)"
                    target="_blank"
                    class="text-sky-400 hover:underline font-medium truncate"
                    :title="att.filename"
                  >
                    {{ att.filename }}
                  </a>
                  <span class="text-[10px] text-slate-500 font-mono shrink-0">({{ formatFileSize(att.filesize) }})</span>
                  <span v-if="att.author" class="text-[10px] text-slate-500 shrink-0">&bull; {{ att.author.name }}</span>
                </div>
                <a
                  :href="getAttachmentUrl(att)"
                  target="_blank"
                  class="p-1 rounded text-slate-400 hover:text-white hover:bg-[#202737] transition-colors shrink-0"
                  title="Download / Open"
                >
                  <Download class="w-3.5 h-3.5" />
                </a>
              </div>
            </div>
          </div>

          <!-- Divider -->
          <hr class="border-[#273245] my-2" />

          <!-- Subtasks Row -->
          <div class="flex items-center justify-between text-[11px]">
            <span class="font-bold text-slate-300">Subtasks</span>
            <button
              type="button"
              class="text-sky-400 hover:underline cursor-pointer"
              @click="handleOpenEdit"
            >
              Add
            </button>
          </div>

          <!-- Divider -->
          <hr class="border-[#273245] my-2" />

          <!-- Related Issues Row -->
          <div class="flex items-center justify-between text-[11px]">
            <span class="font-bold text-slate-300">Related issues</span>
            <button
              type="button"
              class="text-sky-400 hover:underline cursor-pointer"
              @click="handleOpenEdit"
            >
              Add
            </button>
          </div>
        </div>

        <!-- Bottom Action Buttons Bar (Repeated in Classic Redmine) -->
        <div class="flex items-center justify-end space-x-3 text-[11px] text-slate-400 select-none pt-1">
          <button
            type="button"
            class="flex items-center space-x-1 text-sky-400 hover:text-sky-300 hover:underline cursor-pointer font-medium"
            @click="handleOpenEdit"
          >
            <Pencil class="w-3.5 h-3.5 text-amber-400" />
            <span>Edit</span>
          </button>
          <button
            type="button"
            class="flex items-center space-x-1 text-sky-400 hover:text-sky-300 hover:underline cursor-pointer font-medium"
            @click="handleOpenEdit"
          >
            <Clock class="w-3.5 h-3.5 text-emerald-400" />
            <span>Log time</span>
          </button>
          <button
            type="button"
            class="flex items-center space-x-1 text-sky-400 hover:text-sky-300 hover:underline cursor-pointer font-medium"
            @click="isWatching = !isWatching"
          >
            <Star class="w-3.5 h-3.5" :class="isWatching ? 'text-amber-400 fill-amber-400' : 'text-slate-400'" />
            <span>{{ isWatching ? 'Unwatch' : 'Watch' }}</span>
          </button>
          <button
            type="button"
            class="flex items-center space-x-1 text-slate-400 hover:text-rose-400 hover:underline cursor-pointer font-medium"
            @click="emit('close')"
          >
            <Trash2 class="w-3.5 h-3.5 text-slate-400" />
            <span>Delete</span>
          </button>
        </div>

        <!-- Redmine Web Edit Form Component (With 4 Dropdowns, Wiki Toolbar, and Drag & Drop Uploads) -->
        <div ref="editFormContainerRef">
          <RedmineIssueEditForm
            v-if="showEditForm"
            ref="editFormRef"
            :issue="props.issue"
            :statuses="props.statuses"
            :priorities="props.priorities"
            :users="props.users"
            :is-loading="props.isLoading"
            :upload-attachment="props.uploadAttachment"
            @close="showEditForm = false"
            @submit="handleFormSubmit"
          />
        </div>

        <!-- History Section (Identical to Web Screenshot in Image 2 - Requirement 1) -->
        <div class="space-y-3 pt-2">
          <h3 class="text-base font-bold text-white border-b border-[#283447] pb-1.5 flex items-center justify-between">
            <span>History</span>
            <span v-if="props.issue.journals" class="text-xs font-normal text-slate-400">
              {{ props.issue.journals.length }} updates
            </span>
          </h3>

          <div v-if="props.issue.journals && props.issue.journals.length > 0" class="space-y-4">
            <div
              v-for="(j, idx) in props.issue.journals"
              :key="j.id || idx"
              class="border-b border-[#21293a] pb-3 space-y-2"
            >
              <!-- Journal Title Bar: "#N Author • Date Time" matching Screenshot 2 -->
              <div class="flex items-center justify-between text-xs">
                <div class="flex items-center space-x-1.5 flex-wrap">
                  <span class="text-sky-400 font-bold font-mono">#{{ idx + 1 }}</span>
                  <span class="text-slate-100 hover:text-sky-300 hover:underline cursor-pointer font-bold">
                    {{ j.user?.name || 'Anonymous' }}
                  </span>
                  <span class="text-slate-400">&bull; {{ formatJournalDate(j.created_on) }}</span>
                </div>
              </div>

              <!-- Property details / diff list formatted with proper human-readable names and values -->
              <ul v-if="j.details && j.details.length > 0" class="text-xs text-slate-300 space-y-1 pl-1">
                <li
                  v-for="(d, dIdx) in j.details"
                  :key="dIdx"
                  class="flex items-start space-x-1.5"
                >
                  <span class="text-slate-400 select-none font-bold">▸</span>
                  <span class="leading-relaxed" v-html="formatJournalDetail(d).html"></span>
                </li>
              </ul>

              <!-- Journal Notes Body -->
              <div v-if="j.notes" class="text-xs text-slate-200 bg-[#141822] border border-[#222a39] rounded p-3 leading-relaxed select-text space-y-2">
                <template v-for="(part, npIdx) in parseWikiContent(j.notes)" :key="npIdx">
                  <div v-if="part.type === 'text'" class="whitespace-pre-wrap leading-relaxed">{{ part.text }}</div>
                  <div v-else-if="part.type === 'image'" class="my-2">
                    <div
                      class="inline-block max-w-full rounded border border-[#2b3548] bg-[#0c1017] shadow cursor-pointer group hover:border-sky-500/70 transition-all overflow-hidden"
                      @click="lightboxImage = { url: getImageSrc(part.attachment, part.url), title: part.filename || 'Image' }"
                    >
                      <img
                        :src="getImageSrc(part.attachment, part.url)"
                        :alt="part.filename"
                        class="max-w-full max-h-[450px] object-contain block"
                        loading="lazy"
                      />
                      <div class="px-2.5 py-1 text-[10px] text-slate-400 bg-[#141924] border-t border-[#222a3a] flex items-center justify-between">
                        <span class="font-mono text-slate-300 truncate mr-2">{{ part.filename }}</span>
                        <span class="text-sky-400 flex items-center space-x-1">
                          <ZoomIn class="w-2.5 h-2.5" />
                          <span>Zoom</span>
                        </span>
                      </div>
                    </div>
                  </div>
                </template>
              </div>
            </div>
          </div>

          <div v-else class="py-4 text-slate-500 text-xs italic">
            No history recorded yet for this task.
          </div>
        </div>
      </div>
    </div>

    <!-- Image Lightbox Modal for Full View -->
    <Teleport to="body">
      <div
        v-if="lightboxImage"
        class="fixed inset-0 z-[99999] bg-black/85 backdrop-blur-sm flex flex-col items-center justify-center p-4 select-none"
        @click="lightboxImage = null"
      >
        <div class="w-full max-w-5xl flex items-center justify-between text-white pb-3 px-2" @click.stop>
          <span class="text-sm font-semibold truncate">{{ lightboxImage.title }}</span>
          <div class="flex items-center space-x-2">
            <a
              :href="lightboxImage.url"
              target="_blank"
              class="px-2.5 py-1 rounded bg-[#202737] hover:bg-[#2b3548] text-xs text-sky-400 flex items-center space-x-1"
              title="Open full size / Download"
              @click.stop
            >
              <Download class="w-3.5 h-3.5" />
              <span>Download</span>
            </a>
            <button
              type="button"
              class="p-1 rounded bg-black/50 hover:bg-rose-600 text-white transition-colors cursor-pointer"
              @click="lightboxImage = null"
            >
              <X class="w-5 h-5" />
            </button>
          </div>
        </div>

        <div class="max-w-5xl max-h-[85vh] overflow-hidden flex items-center justify-center" @click.stop>
          <img
            :src="lightboxImage.url"
            :alt="lightboxImage.title"
            class="max-w-full max-h-[80vh] object-contain rounded shadow-2xl border border-[#2b3548]"
          />
        </div>
      </div>
    </Teleport>
  </div>
</template>
