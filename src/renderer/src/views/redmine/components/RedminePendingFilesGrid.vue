<script setup lang="ts">
import { File as FileIcon, X } from 'lucide-vue-next'
import { formatFileSize } from '../utils/issueDisplay'

export interface PendingUploadFile {
  id: string
  file: File
  name: string
  size: number
  isImage: boolean
  previewUrl?: string
  description?: string
}

const props = defineProps<{
  files: PendingUploadFile[]
}>()

const emit = defineEmits<{
  (e: 'remove', index: number): void
}>()
</script>

<template>
  <div v-if="props.files.length > 0" class="space-y-1.5 pt-1">
    <div class="text-[11px] font-bold text-slate-400 flex items-center justify-between">
      <span>Files to be uploaded ({{ props.files.length }}):</span>
      <span class="text-[10px] text-slate-500 font-normal">Will be attached when submitted</span>
    </div>

    <div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2">
      <div
        v-for="(pf, idx) in props.files"
        :key="pf.id"
        class="relative border border-[#2b364a] bg-[#141822] rounded-lg p-2 flex flex-col space-y-1 shadow-sm group hover:border-[#3a4964] transition-colors"
      >
        <button
          type="button"
          class="absolute top-1.5 right-1.5 w-5 h-5 rounded-full bg-black/60 hover:bg-rose-600 text-slate-300 hover:text-white flex items-center justify-center transition-colors cursor-pointer z-10"
          title="Remove file"
          @click.stop="emit('remove', idx)"
        >
          <X class="w-3 h-3" />
        </button>

        <div
          v-if="pf.isImage"
          class="w-full h-24 rounded overflow-hidden bg-black/40 flex items-center justify-center border border-[#222a3a]"
        >
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
        <div
          v-else
          class="w-full h-16 rounded bg-[#1a2130] flex flex-col items-center justify-center text-slate-400 border border-[#222a3a]"
        >
          <FileIcon class="w-7 h-7 text-sky-400 mb-0.5" />
          <span class="text-[10px] uppercase font-bold text-slate-500 font-mono">
            {{ pf.name.split('.').pop() || 'FILE' }}
          </span>
        </div>

        <div class="text-xs truncate font-medium text-slate-200 select-text" :title="pf.name">
          {{ pf.name }}
        </div>
        <div class="text-[10px] text-slate-500 font-mono">
          {{ formatFileSize(pf.size) }}
        </div>

        <input
          v-model="pf.description"
          type="text"
          placeholder="Description (optional)"
          class="w-full px-2 py-1 bg-[#1a202c] border border-[#283447] rounded-lg text-[11px] text-slate-200 placeholder-slate-500 focus:outline-none focus:border-blue-500"
        />
      </div>
    </div>
  </div>
</template>

