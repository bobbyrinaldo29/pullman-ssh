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
          <a
            :href="props.resolveImageSrc(att)"
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

    <div v-if="fileAttachments.length > 0" class="space-y-1.5 pt-1">
      <div
        v-for="att in fileAttachments"
        :key="att.id"
        class="flex items-center justify-between px-3 py-1.5 rounded bg-[#141822] border border-[#242e40] text-xs hover:border-[#323f54] transition-colors"
      >
        <div class="flex items-center space-x-2 truncate">
          <FileText class="w-4 h-4 text-sky-400 shrink-0" />
          <a
            :href="props.resolveDownloadUrl(att)"
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
          :href="props.resolveDownloadUrl(att)"
          target="_blank"
          class="p-1 rounded text-slate-400 hover:text-white hover:bg-[#202737] transition-colors shrink-0"
          title="Download / Open"
        >
          <Download class="w-3.5 h-3.5" />
        </a>
      </div>
    </div>
  </div>
</template>

