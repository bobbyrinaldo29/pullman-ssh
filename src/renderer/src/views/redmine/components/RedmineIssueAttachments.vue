<script setup lang="ts">
import { computed } from 'vue'
import { Paperclip, ZoomIn, Download, FileText } from 'lucide-vue-next'
import type { RedmineAttachment } from '../types'
import { formatFileSize, isImageFile } from '../utils/issueDisplay'

const props = defineProps<{
  attachments: RedmineAttachment[]
  resolveImageSrc: (att?: RedmineAttachment | null, fallbackUrl?: string) => string
  resolveDownloadUrl: (att: { content_url: string }) => string
}>()

const emit = defineEmits<{
  (e: 'open-lightbox', payload: { url: string; title: string }): void
}>()

const imageAttachments = computed(() => props.attachments.filter((a) => isImageFile(a.filename)))
const fileAttachments = computed(() => props.attachments.filter((a) => !isImageFile(a.filename)))

async function handleDownloadAttachment(att: RedmineAttachment): Promise<void> {
  const filename = att.filename || 'download'
  const src = props.resolveImageSrc ? props.resolveImageSrc(att) : ''
  const downloadUrl = props.resolveDownloadUrl ? props.resolveDownloadUrl(att) : ''
  const effectiveUrl = src && src.startsWith('data:') ? src : downloadUrl

  if (!effectiveUrl) return

  if (effectiveUrl.startsWith('data:')) {
    const base64Data = effectiveUrl.split(',')[1] || ''
    if (window.api?.saveFileDialog) {
      await window.api.saveFileDialog({
        title: `Save ${filename}`,
        defaultPath: filename,
        base64: base64Data
      })
      return
    }

    const a = document.createElement('a')
    a.href = effectiveUrl
    a.download = filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    return
  }

  if (window.api?.saveFileDialog) {
    try {
      const res = await fetch(effectiveUrl)
      const arrayBuf = await res.arrayBuffer()
      const bytes = new Uint8Array(arrayBuf)
      let binary = ''
      const len = bytes.byteLength
      for (let i = 0; i < len; i++) {
        binary += String.fromCharCode(bytes[i])
      }
      const base64Data = btoa(binary)
      await window.api.saveFileDialog({
        title: `Save ${filename}`,
        defaultPath: filename,
        base64: base64Data
      })
      return
    } catch (err) {
      console.warn('[RedmineIssueAttachments] Fetch fallback:', err)
    }
  }

  const a = document.createElement('a')
  a.href = effectiveUrl
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
}
</script>

<template>
  <div v-if="props.attachments.length > 0" class="space-y-2 pt-2 border-t border-[#273245]">
    <div class="flex items-center space-x-2 text-xs font-bold text-slate-300">
      <Paperclip class="w-3.5 h-3.5 text-sky-400" />
      <span>Files / Attachments ({{ props.attachments.length }})</span>
    </div>

    <div
      v-if="imageAttachments.length > 0"
      class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3 py-1"
    >
      <div
        v-for="att in imageAttachments"
        :key="att.id"
        class="group relative border border-[#2b364a] rounded-lg overflow-hidden bg-[#11151f] hover:border-sky-500/60 transition-all shadow-sm flex flex-col cursor-pointer"
        @click="emit('open-lightbox', { url: props.resolveImageSrc(att), title: att.filename })"
      >
        <div class="w-full h-32 bg-black/50 overflow-hidden flex items-center justify-center relative">
          <img
            :src="props.resolveImageSrc(att)"
            :alt="att.filename"
            class="w-full h-full object-contain group-hover:scale-105 transition-transform duration-200"
            loading="lazy"
          />
          <div class="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 flex items-center justify-center transition-opacity text-white">
            <ZoomIn class="w-6 h-6 text-sky-300 drop-shadow" />
          </div>
        </div>

        <div class="p-2 flex items-center justify-between text-[11px] bg-[#161b26] border-t border-[#242d3d]">
          <div class="truncate mr-1">
            <div class="font-medium text-slate-200 truncate select-text" :title="att.filename">{{ att.filename }}</div>
            <div class="text-[10px] text-slate-500 font-mono">{{ formatFileSize(att.filesize) }}</div>
          </div>
          <button
            type="button"
            class="p-1 text-slate-400 hover:text-sky-300 hover:bg-[#202737] rounded-lg transition-colors cursor-pointer"
            title="Download file"
            @click.stop="handleDownloadAttachment(att)"
          >
            <Download class="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </div>

    <div v-if="fileAttachments.length > 0" class="space-y-1.5 pt-1">
      <div
        v-for="att in fileAttachments"
        :key="att.id"
        class="flex items-center justify-between px-3 py-1.5 rounded-lg bg-[#141822] border border-[#242e40] text-xs hover:border-[#323f54] transition-colors"
      >
        <div class="flex items-center space-x-2 truncate">
          <FileText class="w-4 h-4 text-sky-400 shrink-0" />
          <button
            type="button"
            class="text-sky-400 hover:underline font-medium truncate text-left cursor-pointer"
            :title="`Download ${att.filename}`"
            @click="handleDownloadAttachment(att)"
          >
            {{ att.filename }}
          </button>
          <span class="text-[10px] text-slate-500 font-mono shrink-0">({{ formatFileSize(att.filesize) }})</span>
          <span v-if="att.author" class="text-[10px] text-slate-500 shrink-0">&bull; {{ att.author.name }}</span>
        </div>
        <button
          type="button"
          class="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-[#202737] transition-colors shrink-0 cursor-pointer"
          title="Download file"
          @click.stop="handleDownloadAttachment(att)"
        >
          <Download class="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  </div>
</template>
