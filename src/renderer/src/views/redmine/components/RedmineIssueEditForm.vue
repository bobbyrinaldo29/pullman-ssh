<script setup lang="ts">
import { ref, computed, nextTick, onUnmounted, watch } from 'vue'
import { Pencil, Check, RotateCw, Upload, X, Paperclip, Eye } from 'lucide-vue-next'
import type { RedmineIssue, RedmineStatus, RedminePriority, RedmineUploadItem } from '../types'
import { parseWikiContent, TOOLBAR_SNIPPETS } from '../utils/issueDisplay'
import RedmineWikiToolbar from './RedmineWikiToolbar.vue'
import RedmineWikiContent from './RedmineWikiContent.vue'
import RedminePendingFilesGrid, { type PendingUploadFile } from './RedminePendingFilesGrid.vue'

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
  (e: 'content-resized'): void
  (e: 'submit', payload: {
    status_id?: number
    priority_id?: number
    assigned_to_id?: number
    done_ratio?: number
    notes?: string
    uploads?: RedmineUploadItem[]
  }): void
}>()

const editStatusId = ref<number | undefined>(props.issue.status?.id)
const editPriorityId = ref<number | undefined>(props.issue.priority?.id)
const editAssigneeId = ref<number | undefined>(props.issue.assigned_to?.id)
const editDoneRatio = ref<number>(props.issue.done_ratio || 0)
const editNotes = ref<string>('')
const noteMode = ref<'edit' | 'preview'>('edit')
const textareaRef = ref<HTMLTextAreaElement | null>(null)

const pendingFiles = ref<PendingUploadFile[]>([])
const isDragging = ref(false)
const fileInputRef = ref<HTMLInputElement | null>(null)
const isUploading = ref(false)
const uploadProgressText = ref('')

watch(
  () => props.issue.id,
  () => {
    editStatusId.value = props.issue.status?.id
    editPriorityId.value = props.issue.priority?.id
    editAssigneeId.value = props.issue.assigned_to?.id
    editDoneRatio.value = props.issue.done_ratio || 0
  }
)

const assignableUsers = computed(() => {
  const map = new Map<number, { id: number; name: string }>()
  if (props.issue.assigned_to) map.set(props.issue.assigned_to.id, props.issue.assigned_to)
  if (props.issue.author) map.set(props.issue.author.id, props.issue.author)
  for (const u of props.users || []) map.set(u.id, u)
  return Array.from(map.values())
})

function getNextPastedImageName(extension = 'png'): string {
  const existingNames = new Set(pendingFiles.value.map((f) => f.name.toLowerCase()))
  for (const att of props.issue.attachments || []) {
    existingNames.add(att.filename.toLowerCase())
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
  const insertion = `${prefix}${textToInsert}\n`

  editNotes.value = before + insertion + after

  nextTick(() => {
    el.focus({ preventScroll: true })
    const newPos = start + insertion.length
    el.setSelectionRange(newPos, newPos)
  })
}

function addFiles(files: FileList | File[], autoInsertWikiSyntax = true): void {
  const insertedCommands: string[] = []

  for (let i = 0; i < files.length; i++) {
    const f = files[i]
    if (pendingFiles.value.some((pf) => pf.name === f.name && pf.size === f.size)) continue

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
        if (typeof reader.result === 'string') newFile.previewUrl = reader.result
      }
      reader.readAsDataURL(f)
      if (autoInsertWikiSyntax) insertedCommands.push(`!${f.name}!`)
    }
  }

  if (insertedCommands.length > 0) insertTextAtCursor(insertedCommands.join('\n'))
  nextTick(() => emit('content-resized'))
}

function removeFile(index: number): void {
  const item = pendingFiles.value[index]
  if (item?.previewUrl?.startsWith('blob:')) URL.revokeObjectURL(item.previewUrl)
  pendingFiles.value.splice(index, 1)
}

function handleDrop(e: DragEvent): void {
  e.preventDefault()
  isDragging.value = false
  if (e.dataTransfer?.files?.length) addFiles(e.dataTransfer.files, true)
}

function handleFileSelect(e: Event): void {
  const target = e.target as HTMLInputElement
  if (target.files?.length) {
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
        const filename = blob.name && blob.name !== 'image.png' ? blob.name : getNextPastedImageName(ext)
        imageFiles.push(new File([blob], filename, { type: blob.type }))
      }
    }
  }

  if (imageFiles.length > 0) {
    e.preventDefault()
    addFiles(imageFiles, true)
  }
}

const parsedNotesParts = computed(() =>
  parseWikiContent(editNotes.value, props.issue.attachments || [], pendingFiles.value)
)
const detectedImageParts = computed(() => parsedNotesParts.value.filter((p) => p.type === 'image' && p.url))

onUnmounted(() => {
  for (const pf of pendingFiles.value) {
    if (pf.previewUrl?.startsWith('blob:')) URL.revokeObjectURL(pf.previewUrl)
  }
})

function handleToolbarAction(type: string): void {
  const el = textareaRef.value
  const snippet = TOOLBAR_SNIPPETS[type]
  if (!el || !snippet) return

  const start = el.selectionStart
  const end = el.selectionEnd
  const selected = editNotes.value.substring(start, end)
  const insertion = selected || snippet.placeholder
  const after = snippet.after || ''

  editNotes.value =
    editNotes.value.substring(0, start) + snippet.before + insertion + after + editNotes.value.substring(end)

  nextTick(() => {
    el.focus({ preventScroll: true })
    el.setSelectionRange(start + snippet.before.length, start + snippet.before.length + insertion.length)
  })
}

async function handleSubmit(): Promise<void> {
  if (isUploading.value || props.isLoading) return
  let uploads: RedmineUploadItem[] | undefined

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
    if (pf.previewUrl?.startsWith('blob:')) URL.revokeObjectURL(pf.previewUrl)
  }
  pendingFiles.value = []
  editNotes.value = ''
}

defineExpose({
  insertQuote: (quote: string) => {
    editNotes.value = `${quote}\n\n`
    noteMode.value = 'edit'
    nextTick(() => textareaRef.value?.focus({ preventScroll: true }))
  },
  focus: () => {
    nextTick(() => textareaRef.value?.focus({ preventScroll: true }))
  }
})
</script>

<template>
  <div
    class="bg-[#171c27] border border-[#283447] rounded-lg p-3.5 sm:p-4 space-y-2.5 shadow-sm select-none"
    @paste="handlePaste"
  >
    <!-- Header -->
    <div class="text-[13px] font-bold text-white border-b border-[#242f42] pb-2 flex items-center justify-between gap-2">
      <span class="flex items-center space-x-1.5">
        <Pencil class="w-3.5 h-3.5 text-amber-400" />
        <span>Change properties &amp; Add notes</span>
      </span>
      <button
        type="button"
        class="p-1 text-slate-400 hover:text-white hover:bg-slate-700/50 rounded-lg transition-colors cursor-pointer text-xs flex items-center space-x-1"
        title="Tutup form edit"
        @click="emit('close')"
      >
        <X class="w-3.5 h-3.5" />
        <span>Cancel</span>
      </button>
    </div>

    <!-- 4 Dropdowns: Status, Priority, Assignee, % Done -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-2.5 text-xs">
      <div>
        <label class="block font-bold text-slate-300 text-[11px] mb-1">Status:</label>
        <select
          v-model="editStatusId"
          class="w-full px-2.5 py-1 bg-[#141822] border border-[#2b3548] rounded-lg text-slate-200 focus:outline-none focus:border-blue-500 font-sans cursor-pointer"
        >
          <option v-for="s in props.statuses" :key="s.id" :value="s.id">{{ s.name }}</option>
        </select>
      </div>
      <div>
        <label class="block font-bold text-slate-300 text-[11px] mb-1">Priority:</label>
        <select
          v-model="editPriorityId"
          class="w-full px-2.5 py-1 bg-[#141822] border border-[#2b3548] rounded-lg text-slate-200 focus:outline-none focus:border-blue-500 font-sans cursor-pointer"
        >
          <option v-for="p in props.priorities" :key="p.id" :value="p.id">{{ p.name }}</option>
        </select>
      </div>
      <div>
        <label class="block font-bold text-slate-300 text-[11px] mb-1">Assignee:</label>
        <select
          v-model="editAssigneeId"
          class="w-full px-2.5 py-1 bg-[#141822] border border-[#2b3548] rounded-lg text-slate-200 focus:outline-none focus:border-blue-500 font-sans cursor-pointer"
        >
          <option :value="undefined">&lt;&lt; Unassigned &gt;&gt;</option>
          <option v-for="u in assignableUsers" :key="u.id" :value="u.id">{{ u.name }}</option>
        </select>
      </div>
      <div>
        <label class="block font-bold text-slate-300 text-[11px] mb-1">% Done:</label>
        <select
          v-model="editDoneRatio"
          class="w-full px-2.5 py-1 bg-[#141822] border border-[#2b3548] rounded-lg text-slate-200 focus:outline-none focus:border-blue-500 font-sans cursor-pointer"
        >
          <option v-for="pct in [0, 20, 40, 60, 80, 100]" :key="pct" :value="pct">{{ pct }}%</option>
        </select>
      </div>
    </div>

    <!-- Notes with Redmine Wiki Formatting Toolbar -->
    <div class="space-y-1">
      <div class="flex items-center justify-between">
        <label class="font-bold text-slate-300 text-[11px]">Notes:</label>
        <span class="text-[10px] text-slate-500">Ctrl+Enter untuk Submit cepat</span>
      </div>

      <RedmineWikiToolbar v-model:active-tab="noteMode" @action="handleToolbarAction" />

      <textarea
        v-show="noteMode === 'edit'"
        ref="textareaRef"
        v-model="editNotes"
        rows="3"
        placeholder="Add a comment or update note here... Paste screenshot (Ctrl+V) or drop images directly to insert !Gambar1.png!"
        class="w-full min-h-[74px] max-h-[260px] px-3 py-2 bg-[#141822] border border-[#2b3548] rounded-b-lg text-slate-200 placeholder-slate-500 focus:outline-none focus:border-blue-500 font-sans resize-y leading-relaxed text-xs select-text"
        @paste="handlePaste"
        @keydown.ctrl.enter.prevent="handleSubmit"
        @dragover.prevent="isDragging = true"
        @dragleave="isDragging = false"
        @drop="handleDrop"
      ></textarea>

      <!-- Live Mini Image Preview in Edit Mode -->
      <div
        v-if="noteMode === 'edit' && detectedImageParts.length > 0"
        class="p-2 bg-[#10141d] border border-[#252f42] rounded-lg text-xs space-y-1.5 mt-1"
      >
        <div class="flex items-center justify-between text-[11px] font-bold text-slate-400">
          <div class="flex items-center space-x-1.5 text-sky-400">
            <Eye class="w-3.5 h-3.5" />
            <span>Gambar Terdeteksi di Notes ({{ detectedImageParts.length }}):</span>
          </div>
          <button
            type="button"
            class="text-[10px] text-sky-400 hover:text-sky-300 underline cursor-pointer"
            @click="noteMode = 'preview'"
          >
            Lihat Preview Penuh &rarr;
          </button>
        </div>

        <div class="flex flex-wrap gap-2">
          <div
            v-for="(part, idx) in detectedImageParts"
            :key="idx"
            class="border border-[#2d374a] rounded bg-[#0a0d14] overflow-hidden max-w-[240px] shadow"
          >
            <div class="h-20 bg-black/50 flex items-center justify-center p-1">
              <img :src="part.url" :alt="part.filename" class="max-w-full max-h-full object-contain" />
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
        class="w-full px-3.5 py-2.5 bg-[#141822] border border-[#2b3548] rounded-b-lg text-slate-200 font-sans min-h-[82px] text-xs leading-relaxed select-text space-y-2"
      >
        <RedmineWikiContent
          :parts="parsedNotesParts"
          max-image-height-class="max-h-[360px]"
          :zoomable="false"
          :preview-mode="true"
          empty-text="Nothing to preview. Type something or paste/drop an image in Edit tab."
        />
      </div>
    </div>

    <!-- Compact Drag & Drop Files Upload Area -->
    <div class="space-y-1.5">
      <div class="flex items-center justify-between text-xs font-semibold text-slate-300">
        <span class="flex items-center space-x-1.5 text-[11px]">
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

      <input ref="fileInputRef" type="file" multiple class="hidden" @change="handleFileSelect" />

      <div
        class="border-2 border-dashed rounded-lg px-3 py-2 text-center cursor-pointer transition-colors"
        :class="
          isDragging
            ? 'border-sky-400 bg-sky-500/10 text-sky-300'
            : 'border-[#2d374a] hover:border-slate-500 bg-[#141822]/60 text-slate-400'
        "
        @dragover.prevent="isDragging = true"
        @dragleave.prevent="isDragging = false"
        @drop="handleDrop"
        @click="fileInputRef?.click()"
      >
        <div class="flex items-center justify-center gap-2 pointer-events-none select-none flex-wrap">
          <Upload class="w-4 h-4 text-slate-400 shrink-0" :class="{ 'text-sky-400 animate-bounce': isDragging }" />
          <span class="text-xs font-medium text-slate-200">
            <span class="text-sky-400 underline">Click to browse</span> or drag and drop files here
          </span>
          <span class="text-[10px] text-slate-500">
            &bull; Paste screenshot <kbd class="px-1 py-0.5 rounded bg-[#1e2534] border border-[#2d374a] text-slate-300">Ctrl+V</kbd>
          </span>
        </div>
      </div>

      <RedminePendingFilesGrid :files="pendingFiles" @remove="removeFile" />
    </div>

    <!-- Submit Actions Footer -->
    <div class="flex items-center justify-between pt-2 border-t border-[#222d3d] gap-3">
      <div class="text-xs text-sky-400 font-medium truncate">
        <span v-if="uploadProgressText">{{ uploadProgressText }}</span>
      </div>

      <div class="flex items-center space-x-2 shrink-0">
        <button
          type="button"
          class="px-3.5 py-1.5 rounded-lg border border-[#2D3547] bg-[#252B3A] hover:bg-[#2F374A] text-slate-300 hover:text-white text-xs font-medium transition-colors flex items-center space-x-1.5 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
          :disabled="isUploading || props.isLoading"
          @click="emit('close')"
        >
          <span>Cancel</span>
        </button>
        <button
          type="button"
          class="px-4 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-medium text-xs transition-colors shadow-sm disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-1.5 cursor-pointer"
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
