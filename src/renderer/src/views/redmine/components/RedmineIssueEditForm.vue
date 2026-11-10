<script setup lang="ts">
import { ref, computed, nextTick, onUnmounted } from 'vue'
import {
  Pencil,
  Check,
  RotateCw,
  Upload,
  File as FileIcon,
  X,
  Paperclip,
  Eye
} from 'lucide-vue-next'
import { RedmineIssue, RedmineStatus, RedminePriority } from '../types'
import RedmineWikiToolbar from './RedmineWikiToolbar.vue'

interface PendingUploadFile {
  id: string
  file: File
  name: string
  size: number
  isImage: boolean
  previewUrl?: string
  description?: string
}

const props = defineProps<{
  issue: RedmineIssue
  statuses: RedmineStatus[]
  priorities: RedminePriority[]
  isLoading: boolean
  users?: Array<{ id: number; name: string }>
  uploadAttachment?: (file: File) => Promise<{ success: boolean; token?: string; error?: string }>
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'submit', payload: {
    status_id?: number
    priority_id?: number
    assigned_to_id?: number
    done_ratio?: number
    notes?: string
    uploads?: Array<{ token: string; filename: string; description?: string; content_type?: string }>
  }): void
}>()

const editStatusId = ref<number | undefined>(props.issue.status?.id)
const editPriorityId = ref<number | undefined>(props.issue.priority?.id)
const editAssigneeId = ref<number | undefined>(props.issue.assigned_to?.id)
const editDoneRatio = ref<number>(props.issue.done_ratio || 0)
const editNotes = ref<string>('')
const noteMode = ref<'edit' | 'preview'>('edit')
const textareaRef = ref<HTMLTextAreaElement | null>(null)

// Drag & drop file upload state
const pendingFiles = ref<PendingUploadFile[]>([])
const isDragging = ref(false)
const fileInputRef = ref<HTMLInputElement | null>(null)
const isUploading = ref(false)
const uploadProgressText = ref('')

const assignableUsers = computed(() => {
  const map = new Map<number, { id: number; name: string }>()
  if (props.issue.assigned_to) {
    map.set(props.issue.assigned_to.id, props.issue.assigned_to)
  }
  if (props.issue.author) {
    map.set(props.issue.author.id, props.issue.author)
  }
  if (props.users) {
    for (const u of props.users) {
      map.set(u.id, u)
    }
  }
  return Array.from(map.values())
})

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function getNextPastedImageName(extension = 'png'): string {
  const existingNames = new Set(pendingFiles.value.map((f) => f.name.toLowerCase()))
  if (props.issue.attachments) {
    for (const att of props.issue.attachments) {
      existingNames.add(att.filename.toLowerCase())
    }
  }

  let idx = 1
  while (
    existingNames.has(`gambar${idx}.${extension}`) ||
    existingNames.has(`gambar${idx}.png`) ||
    existingNames.has(`gambar${idx}.jpg`)
  ) {
    idx++
  }
  return `Gambar${idx}.${extension}`
}

function insertTextAtCursor(textToInsert: string): void {
  const el = textareaRef.value
  if (!el) {
    const trimmed = editNotes.value.trim()
    editNotes.value = trimmed ? `${trimmed}\n\n${textToInsert}\n` : `${textToInsert}\n`
    return
  }

  const start = el.selectionStart ?? editNotes.value.length
  const end = el.selectionEnd ?? editNotes.value.length
  const before = editNotes.value.substring(0, start)
  const after = editNotes.value.substring(end)

  const prefix = before.length > 0 && !before.endsWith('\n') ? '\n' : ''
  const suffix = after.length > 0 && !after.startsWith('\n') ? '\n' : '\n'
  const insertion = `${prefix}${textToInsert}${suffix}`

  editNotes.value = before + insertion + after

  nextTick(() => {
    el.focus()
    const newPos = start + insertion.length
    el.setSelectionRange(newPos, newPos)
  })
}

function addFiles(files: FileList | File[], autoInsertWikiSyntax = true): void {
  const insertedCommands: string[] = []

  for (let i = 0; i < files.length; i++) {
    const f = files[i]
    if (pendingFiles.value.some((pf) => pf.name === f.name && pf.size === f.size)) {
      continue
    }

    const isImg = f.type.startsWith('image/') || /\.(png|jpe?g|gif|webp|svg|bmp)$/i.test(f.name)
    const newFile: PendingUploadFile = {
      id: `${Date.now()}-${Math.random().toString(36).substring(2, 9)}`,
      file: f,
      name: f.name,
      size: f.size,
      isImage: isImg,
      previewUrl: isImg ? URL.createObjectURL(f) : undefined,
      description: ''
    }

    pendingFiles.value.push(newFile)

    if (isImg) {
      const reader = new FileReader()
      reader.onload = (): void => {
        if (typeof reader.result === 'string') {
          newFile.previewUrl = reader.result
        }
      }
      reader.readAsDataURL(f)

      if (autoInsertWikiSyntax) {
        insertedCommands.push(`!${f.name}!`)
      }
    }
  }

  if (insertedCommands.length > 0) {
    insertTextAtCursor(insertedCommands.join('\n'))
  }
}

function removeFile(index: number): void {
  const item = pendingFiles.value[index]
  if (item?.previewUrl && item.previewUrl.startsWith('blob:')) {
    URL.revokeObjectURL(item.previewUrl)
  }
  pendingFiles.value.splice(index, 1)
}

function handleDragOver(e: DragEvent): void {
  e.preventDefault()
  isDragging.value = true
}

function handleDragLeave(e: DragEvent): void {
  e.preventDefault()
  isDragging.value = false
}

function handleDrop(e: DragEvent): void {
  e.preventDefault()
  isDragging.value = false
  if (e.dataTransfer?.files && e.dataTransfer.files.length > 0) {
    addFiles(e.dataTransfer.files, true)
  }
}

function handleFileSelect(e: Event): void {
  const target = e.target as HTMLInputElement
  if (target.files && target.files.length > 0) {
    addFiles(target.files, true)
    target.value = ''
  }
}

function handlePaste(e: ClipboardEvent): void {
  if (!e.clipboardData?.items) return
  const imageFiles: File[] = []

  for (let i = 0; i < e.clipboardData.items.length; i++) {
    const item = e.clipboardData.items[i]
    if (item.kind === 'file' && item.type.startsWith('image/')) {
      const blob = item.getAsFile()
      if (blob) {
        const ext = (blob.type.split('/')[1] || 'png').replace('jpeg', 'jpg')
        const filename =
          blob.name && blob.name !== 'image.png'
            ? blob.name
            : getNextPastedImageName(ext)
        const namedFile = new File([blob], filename, { type: blob.type })
        imageFiles.push(namedFile)
      }
    }
  }

  if (imageFiles.length > 0) {
    e.preventDefault()
    addFiles(imageFiles, true)
  }
}

interface NoteBlockPart {
  type: 'text' | 'image'
  text?: string
  filename?: string
  url?: string
}

const parsedNotesParts = computed<NoteBlockPart[]>(() => {
  if (!editNotes.value) return []
  const text = editNotes.value
  const parts: NoteBlockPart[] = []

  const imgRegex = /!(?:\{.*?\})?(?:<|>|=)?([^\s!]+?\.(?:png|jpe?g|gif|webp|svg|bmp))(?:\([^\)]*?\))?!/gi
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

    const rawFilename = match[1].trim()
    const isHttp = rawFilename.startsWith('http://') || rawFilename.startsWith('https://')

    // 1. Search in pendingFiles (uploaded in this edit session)
    const pendingMatch = pendingFiles.value.find(
      (pf) =>
        pf.name.toLowerCase() === rawFilename.toLowerCase() ||
        rawFilename.toLowerCase().endsWith(pf.name.toLowerCase())
    )

    // 2. Search in existing issue attachments
    const issueMatch = (props.issue.attachments || []).find(
      (att) =>
        att.filename.toLowerCase() === rawFilename.toLowerCase() ||
        rawFilename.toLowerCase().endsWith(att.filename.toLowerCase())
    )

    if (pendingMatch) {
      parts.push({
        type: 'image',
        filename: pendingMatch.name,
        url: pendingMatch.previewUrl
      })
    } else if (issueMatch) {
      parts.push({
        type: 'image',
        filename: issueMatch.filename,
        url: issueMatch.content_url
      })
    } else if (isHttp) {
      parts.push({
        type: 'image',
        filename: rawFilename.split('/').pop() || 'image',
        url: rawFilename
      })
    } else {
      parts.push({
        type: 'image',
        filename: rawFilename,
        url: ''
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
})

onUnmounted(() => {
  for (const pf of pendingFiles.value) {
    if (pf.previewUrl && pf.previewUrl.startsWith('blob:')) URL.revokeObjectURL(pf.previewUrl)
  }
})

function handleToolbarAction(type: string): void {
  const el = textareaRef.value
  if (!el) return
  const start = el.selectionStart
  const end = el.selectionEnd
  const sel = editNotes.value.substring(start, end)

  let before = ''
  let after = ''
  let defaultText = 'text'

  switch (type) {
    case 'bold': before = '**'; after = '**'; defaultText = 'Bold text'; break
    case 'italic': before = '_'; after = '_'; defaultText = 'Italic text'; break
    case 'underline': before = '+'; after = '+'; defaultText = 'Underlined text'; break
    case 'strike': before = '-'; after = '-'; defaultText = 'Deleted text'; break
    case 'code': before = '@'; after = '@'; defaultText = 'code'; break
    case 'h1': before = '\nh1. '; defaultText = 'Heading 1'; break
    case 'h2': before = '\nh2. '; defaultText = 'Heading 2'; break
    case 'h3': before = '\nh3. '; defaultText = 'Heading 3'; break
    case 'ul': before = '\n* '; defaultText = 'Bullet item'; break
    case 'ol': before = '\n# '; defaultText = 'Numbered item'; break
    case 'indent': before = '\n> '; defaultText = 'Quoted text'; break
    case 'outdent': before = '\n'; defaultText = ''; break
    case 'pre': before = '\n<pre>\n'; after = '\n</pre>\n'; defaultText = 'Preformatted block'; break
    case 'code-block': before = '\n<pre><code class="sql">\n'; after = '\n</code></pre>\n'; defaultText = '-- Code here'; break
    case 'link': before = '"'; after = '":https://example.com'; defaultText = 'Link title'; break
    case 'image': before = '!'; after = '!'; defaultText = 'https://example.com/image.png'; break
    case 'help': before = '\n\n*Formatting:* **bold**, _italic_, +underline+, -strike-, @inline code@, h1. Heading\n'; defaultText = ''; break
  }

  const insertion = sel || defaultText
  editNotes.value = editNotes.value.substring(0, start) + before + insertion + after + editNotes.value.substring(end)
  nextTick(() => {
    el.focus()
    el.setSelectionRange(start + before.length, start + before.length + insertion.length)
  })
}

async function handleSubmit(): Promise<void> {
  let uploads: Array<{ token: string; filename: string; description?: string; content_type?: string }> | undefined = undefined

  if (pendingFiles.value.length > 0 && props.uploadAttachment) {
    isUploading.value = true
    uploads = []
    for (let i = 0; i < pendingFiles.value.length; i++) {
      const pf = pendingFiles.value[i]
      uploadProgressText.value = `Uploading ${pf.name} (${i + 1}/${pendingFiles.value.length})...`
      const res = await props.uploadAttachment(pf.file)
      if (res.success && res.token) {
        uploads.push({
          token: res.token,
          filename: pf.name,
          description: pf.description?.trim() || undefined,
          content_type: pf.file.type || undefined
        })
      } else {
        alert(`Failed to upload ${pf.name}: ${res.error || 'Unknown error'}`)
        isUploading.value = false
        uploadProgressText.value = ''
        return
      }
    }
    isUploading.value = false
    uploadProgressText.value = ''
  }

  emit('submit', {
    status_id: editStatusId.value,
    priority_id: editPriorityId.value,
    assigned_to_id: editAssigneeId.value,
    done_ratio: Number(editDoneRatio.value),
    notes: editNotes.value.trim() || undefined,
    uploads
  })

  for (const pf of pendingFiles.value) {
    if (pf.previewUrl) URL.revokeObjectURL(pf.previewUrl)
  }
  pendingFiles.value = []
  editNotes.value = ''
}

defineExpose({
  insertQuote: (quote: string) => {
    editNotes.value = `${quote}\n\n`
    noteMode.value = 'edit'
    nextTick(() => {
      textareaRef.value?.focus()
    })
  },
  focus: () => {
    nextTick(() => {
      textareaRef.value?.focus()
    })
  }
})
</script>

<template>
  <div
    class="bg-[#171c27] border border-[#283447] rounded-md p-5 space-y-4 shadow-sm select-none"
    @paste="handlePaste"
  >
    <h4 class="text-[13px] font-bold text-white border-b border-[#242f42] pb-1.5 flex items-center justify-between">
      <span class="flex items-center space-x-1.5">
        <Pencil class="w-3.5 h-3.5 text-amber-400" />
        <span>Change properties & Add notes</span>
      </span>
      <button
        type="button"
        class="text-xs text-slate-400 hover:text-white cursor-pointer"
        @click="emit('close')"
      >
        &times; Cancel
      </button>
    </h4>

    <!-- 4 Dropdowns: Status, Priority, Assignee, % Done -->
    <div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3 text-xs">
      <div>
        <label class="block font-bold text-slate-300 mb-1">Status:</label>
        <select
          v-model="editStatusId"
          class="w-full px-2.5 py-1.5 bg-[#141822] border border-[#2b3548] rounded text-slate-200 focus:outline-none focus:border-blue-500 font-sans cursor-pointer"
        >
          <option v-for="s in props.statuses" :key="s.id" :value="s.id">
            {{ s.name }}
          </option>
        </select>
      </div>
      <div>
        <label class="block font-bold text-slate-300 mb-1">Priority:</label>
        <select
          v-model="editPriorityId"
          class="w-full px-2.5 py-1.5 bg-[#141822] border border-[#2b3548] rounded text-slate-200 focus:outline-none focus:border-blue-500 font-sans cursor-pointer"
        >
          <option v-for="p in props.priorities" :key="p.id" :value="p.id">
            {{ p.name }}
          </option>
        </select>
      </div>
      <div>
        <label class="block font-bold text-slate-300 mb-1">Assignee:</label>
        <select
          v-model="editAssigneeId"
          class="w-full px-2.5 py-1.5 bg-[#141822] border border-[#2b3548] rounded text-slate-200 focus:outline-none focus:border-blue-500 font-sans cursor-pointer"
        >
          <option :value="undefined">&lt;&lt; Unassigned &gt;&gt;</option>
          <option v-for="u in assignableUsers" :key="u.id" :value="u.id">
            {{ u.name }}
          </option>
        </select>
      </div>
      <div>
        <label class="block font-bold text-slate-300 mb-1">% Done:</label>
        <select
          v-model="editDoneRatio"
          class="w-full px-2.5 py-1.5 bg-[#141822] border border-[#2b3548] rounded text-slate-200 focus:outline-none focus:border-blue-500 font-sans cursor-pointer"
        >
          <option :value="0">0%</option>
          <option :value="20">20%</option>
          <option :value="40">40%</option>
          <option :value="60">60%</option>
          <option :value="80">80%</option>
          <option :value="100">100%</option>
        </select>
      </div>
    </div>

    <!-- Notes with Redmine Wiki Formatting Toolbar -->
    <div class="space-y-1.5">
      <label class="block font-bold text-slate-300 mb-0.5">Notes:</label>

      <!-- Wiki Toolbar -->
      <RedmineWikiToolbar
        v-model:active-tab="noteMode"
        @action="handleToolbarAction"
      />

      <!-- Edit Textarea Area -->
      <textarea
        v-show="noteMode === 'edit'"
        ref="textareaRef"
        v-model="editNotes"
        rows="5"
        placeholder="Add a comment or update note here... Paste screenshot (Ctrl+V) or drop images directly to insert !Gambar1.png!"
        class="w-full px-3 py-2 bg-[#141822] border border-[#2b3548] rounded-b text-slate-200 placeholder-slate-500 focus:outline-none focus:border-blue-500 font-sans resize-y leading-relaxed text-xs select-text"
        @paste="handlePaste"
        @dragover.prevent="isDragging = true"
        @dragleave="isDragging = false"
        @drop="handleDrop"
      ></textarea>

      <!-- Live Mini Image Preview in Edit Mode -->
      <div
        v-if="noteMode === 'edit' && parsedNotesParts.some((p) => p.type === 'image' && p.url)"
        class="p-2.5 bg-[#10141d] border border-[#252f42] rounded text-xs space-y-2 mt-1.5"
      >
        <div class="flex items-center justify-between text-[11px] font-bold text-slate-400">
          <div class="flex items-center space-x-1.5 text-sky-400">
            <Eye class="w-3.5 h-3.5" />
            <span>Gambar Terdeteksi di Notes ({{ parsedNotesParts.filter((p) => p.type === 'image' && p.url).length }}):</span>
          </div>
          <button
            type="button"
            class="text-[10px] text-sky-400 hover:text-sky-300 underline cursor-pointer"
            @click="noteMode = 'preview'"
          >
            Lihat Preview Penuh &rarr;
          </button>
        </div>

        <div class="flex flex-wrap gap-2.5">
          <div
            v-for="(part, idx) in parsedNotesParts.filter((p) => p.type === 'image' && p.url)"
            :key="idx"
            class="border border-[#2d374a] rounded bg-[#0a0d14] overflow-hidden max-w-[280px] shadow"
          >
            <div class="h-28 bg-black/50 flex items-center justify-center p-1">
              <img
                :src="part.url"
                :alt="part.filename"
                class="max-w-full max-h-full object-contain"
              />
            </div>
            <div class="px-2 py-1 bg-[#141924] border-t border-[#232b3a] text-[10px] text-slate-300 font-mono truncate flex items-center justify-between">
              <span class="truncate mr-1 font-bold text-sky-300">!{{ part.filename }}!</span>
              <span class="text-[9px] text-emerald-400 shrink-0 font-sans">Ready</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Preview Live Rendering Area -->
      <div
        v-show="noteMode === 'preview'"
        class="w-full px-4 py-3 bg-[#141822] border border-[#2b3548] rounded-b text-slate-200 font-sans min-h-[130px] text-xs leading-relaxed select-text space-y-2"
      >
        <template v-if="parsedNotesParts.length > 0">
          <template v-for="(part, pIdx) in parsedNotesParts" :key="pIdx">
            <!-- Text Part -->
            <div v-if="part.type === 'text'" class="whitespace-pre-wrap leading-relaxed">{{ part.text }}</div>

            <!-- Inline Wiki Image Part (Directly renders !Gambar1.png!) -->
            <div v-else-if="part.type === 'image'" class="my-2.5">
              <div class="inline-block max-w-full rounded-lg border border-[#2b3548] bg-[#0c1017] shadow overflow-hidden group">
                <div v-if="part.url" class="relative flex items-center justify-center bg-black/40 min-h-[60px] min-w-[120px]">
                  <img
                    :src="part.url"
                    :alt="part.filename"
                    class="max-w-full max-h-[450px] object-contain block group-hover:scale-[1.005] transition-transform"
                  />
                </div>
                <div v-else class="p-3 bg-[#1a202c] text-amber-300 text-xs flex items-center space-x-1 font-mono">
                  <span>!{{ part.filename }}!</span>
                  <span class="text-slate-400">(Menunggu upload)</span>
                </div>
                <div class="px-2.5 py-1 text-[10px] text-slate-400 bg-[#141924] border-t border-[#222a3a] flex items-center justify-between font-mono">
                  <span class="text-slate-300 truncate">{{ part.filename }}</span>
                  <span class="text-[9px] text-emerald-400 font-sans">Preview</span>
                </div>
              </div>
            </div>
          </template>
        </template>
        <div v-else class="text-slate-500 italic">
          Nothing to preview. Type something or paste/drop an image in Edit tab.
        </div>
      </div>
    </div>

    <!-- Drag & Drop Files Upload Area -->
    <div class="space-y-2 pt-1">
      <div class="flex items-center justify-between text-xs font-semibold text-slate-300">
        <span class="flex items-center space-x-1.5">
          <Paperclip class="w-3.5 h-3.5 text-sky-400" />
          <span>Files / Attachments</span>
        </span>
        <button
          type="button"
          class="text-sky-400 hover:text-sky-300 hover:underline cursor-pointer text-[11px]"
          @click="fileInputRef?.click()"
        >
          + Choose file
        </button>
      </div>

      <!-- Hidden File Input -->
      <input
        ref="fileInputRef"
        type="file"
        multiple
        class="hidden"
        @change="handleFileSelect"
      />

      <!-- Drag & Drop Box -->
      <div
        class="border-2 border-dashed rounded-lg p-4 text-center cursor-pointer transition-colors"
        :class="
          isDragging
            ? 'border-sky-400 bg-sky-500/10 text-sky-300'
            : 'border-[#2d374a] hover:border-slate-500 bg-[#141822]/60 text-slate-400'
        "
        @dragover="handleDragOver"
        @dragleave="handleDragLeave"
        @drop="handleDrop"
        @click="fileInputRef?.click()"
      >
        <div class="flex flex-col items-center justify-center space-y-1.5 pointer-events-none select-none">
          <Upload class="w-6 h-6 text-slate-400 mb-0.5" :class="{ 'text-sky-400 animate-bounce': isDragging }" />
          <p class="text-xs font-medium text-slate-200">
            <span class="text-sky-400 underline">Click to browse</span> or drag and drop files here
          </p>
          <p class="text-[10px] text-slate-500">
            Images (PNG, JPG, GIF), PDFs, documents. Paste screenshot with <kbd class="px-1 py-0.5 rounded bg-[#1e2534] border border-[#2d374a] text-slate-300">Ctrl+V</kbd>
          </p>
        </div>
      </div>

      <!-- Pending Files / Image Preview Grid -->
      <div v-if="pendingFiles.length > 0" class="space-y-2 pt-1">
        <div class="text-[11px] font-bold text-slate-400 flex items-center justify-between">
          <span>Files to be uploaded ({{ pendingFiles.length }}):</span>
          <span class="text-[10px] text-slate-500 font-normal">Will be attached when submitted</span>
        </div>

        <div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2.5">
          <div
            v-for="(pf, idx) in pendingFiles"
            :key="pf.id"
            class="relative border border-[#2b364a] bg-[#141822] rounded-md p-2 flex flex-col space-y-1.5 shadow-sm group hover:border-[#3a4964] transition-colors"
          >
            <!-- Delete Button -->
            <button
              type="button"
              class="absolute top-1.5 right-1.5 w-5 h-5 rounded-full bg-black/60 hover:bg-rose-600 text-slate-300 hover:text-white flex items-center justify-center transition-colors cursor-pointer z-10"
              title="Remove file"
              @click.stop="removeFile(idx)"
            >
              <X class="w-3 h-3" />
            </button>

            <!-- Image Preview or Document Icon -->
            <div v-if="pf.isImage" class="w-full h-28 rounded overflow-hidden bg-black/40 flex items-center justify-center border border-[#222a3a]">
              <img
                v-if="pf.previewUrl"
                :src="pf.previewUrl"
                :alt="pf.name"
                class="w-full h-full object-contain"
              />
              <div v-else class="text-[10px] text-slate-500 flex items-center justify-center">
                <span>Loading preview...</span>
              </div>
            </div>
            <div v-else class="w-full h-20 rounded bg-[#1a2130] flex flex-col items-center justify-center text-slate-400 border border-[#222a3a]">
              <FileIcon class="w-8 h-8 text-sky-400 mb-1" />
              <span class="text-[10px] uppercase font-bold text-slate-500 font-mono">{{ pf.name.split('.').pop() || 'FILE' }}</span>
            </div>

            <!-- File Name & Size -->
            <div class="text-xs truncate font-medium text-slate-200" :title="pf.name">
              {{ pf.name }}
            </div>
            <div class="text-[10px] text-slate-500 font-mono">
              {{ formatFileSize(pf.size) }}
            </div>

            <!-- Optional Description Input -->
            <input
              v-model="pf.description"
              type="text"
              placeholder="Description (optional)"
              class="w-full px-2 py-1 bg-[#1a202c] border border-[#283447] rounded text-[11px] text-slate-200 placeholder-slate-500 focus:outline-none focus:border-blue-500"
            />
          </div>
        </div>
      </div>
    </div>

    <!-- Submit Actions -->
    <div class="flex items-center justify-between pt-2 border-t border-[#222d3d]">
      <div class="text-xs text-sky-400 font-medium">
        <span v-if="uploadProgressText">{{ uploadProgressText }}</span>
      </div>

      <div class="flex items-center space-x-2">
        <button
          type="button"
          class="px-3 py-1.5 rounded text-xs text-slate-400 hover:text-white hover:bg-[#202737] transition-colors cursor-pointer"
          :disabled="isUploading || props.isLoading"
          @click="emit('close')"
        >
          Cancel
        </button>
        <button
          type="button"
          class="px-4 py-1.5 rounded text-xs font-semibold text-white bg-[#b32d2e] hover:bg-[#c93637] transition-all flex items-center space-x-1.5 cursor-pointer disabled:opacity-50 shadow-sm"
          :disabled="isUploading || props.isLoading"
          @click="handleSubmit"
        >
          <RotateCw v-if="isUploading || props.isLoading" class="w-3.5 h-3.5 animate-spin" />
          <Check v-else class="w-3.5 h-3.5" />
          <span>{{ isUploading ? 'Uploading...' : props.isLoading ? 'Saving...' : 'Submit' }}</span>
        </button>
      </div>
    </div>
  </div>
</template>

