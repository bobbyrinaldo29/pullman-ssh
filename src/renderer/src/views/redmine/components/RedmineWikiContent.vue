<script setup lang="ts">
import { ZoomIn } from 'lucide-vue-next'
import type { RedmineAttachment } from '../types'
import type { TextBlockPart } from '../utils/issueDisplay'

const props = withDefaults(
  defineProps<{
    parts: TextBlockPart[]
    maxImageHeightClass?: string
    zoomable?: boolean
    previewMode?: boolean
    emptyText?: string
    resolveImageSrc?: (att?: RedmineAttachment | null, fallbackUrl?: string) => string
  }>(),
  {
    maxImageHeightClass: 'max-h-[450px]',
    zoomable: true,
    previewMode: false,
    emptyText: '',
    resolveImageSrc: undefined
  }
)

const emit = defineEmits<{
  (e: 'open-lightbox', payload: { url: string; title: string }): void
}>()

function getPartSrc(part: TextBlockPart): string {
  if (props.resolveImageSrc) {
    return props.resolveImageSrc(part.attachment, part.url)
  }
  return part.url || ''
}
</script>

<template>
  <template v-if="props.parts.length > 0">
    <template v-for="(part, idx) in props.parts" :key="idx">
      <div v-if="part.type === 'text'" class="whitespace-pre-wrap leading-relaxed">{{ part.text }}</div>

      <div v-else-if="part.type === 'image'" class="my-2.5">
        <div
          class="inline-block max-w-full rounded-lg border border-[#2b3548] bg-[#0c1017] shadow overflow-hidden group transition-all"
          :class="props.zoomable ? 'cursor-pointer hover:border-sky-500/70' : ''"
          @click="props.zoomable && emit('open-lightbox', { url: getPartSrc(part), title: part.filename || 'Image' })"
        >
          <div
            v-if="getPartSrc(part)"
            class="relative flex items-center justify-center bg-black/40 min-h-[50px] min-w-[120px]"
          >
            <img
              :src="getPartSrc(part)"
              :alt="part.filename"
              class="max-w-full object-contain block group-hover:scale-[1.005] transition-transform"
              :class="props.maxImageHeightClass"
              loading="lazy"
            />
            <div
              v-if="props.zoomable"
              class="absolute top-2 right-2 px-2 py-1 bg-black/75 rounded text-[10px] text-sky-300 opacity-0 group-hover:opacity-100 transition-opacity flex items-center space-x-1 shadow"
            >
              <ZoomIn class="w-3 h-3" />
              <span>Click to zoom</span>
            </div>
          </div>
          <div v-else class="p-3 bg-[#1a202c] text-amber-300 text-xs flex items-center space-x-1 font-mono">
            <span>!{{ part.filename }}!</span>
            <span class="text-slate-400">(Menunggu upload)</span>
          </div>

          <div class="px-2.5 py-1 text-[10px] text-slate-400 bg-[#141924] border-t border-[#222a3a] flex items-center justify-between font-mono">
            <span class="text-slate-300 truncate mr-2">{{ part.filename }}</span>
            <span v-if="props.previewMode" class="text-[9px] text-emerald-400 font-sans shrink-0">Preview</span>
            <span v-else-if="props.zoomable" class="text-sky-400 flex items-center space-x-1 font-sans shrink-0">
              <ZoomIn class="w-2.5 h-2.5" />
              <span>View full size</span>
            </span>
          </div>
        </div>
      </div>
    </template>
  </template>
  <div v-else-if="props.emptyText" class="text-slate-500 italic">
    {{ props.emptyText }}
  </div>
</template>

