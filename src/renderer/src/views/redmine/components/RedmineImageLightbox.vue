<script setup lang="ts">
import { Download, X } from 'lucide-vue-next'

const props = defineProps<{
  image: { url: string; title: string } | null
}>()

const emit = defineEmits<{
  (e: 'close'): void
}>()
</script>

<template>
  <Teleport to="body">
    <div
      v-if="props.image"
      class="fixed inset-0 z-[99999] bg-black/85 backdrop-blur-sm flex flex-col items-center justify-center p-4 select-none"
      @click="emit('close')"
    >
      <div class="w-full max-w-5xl flex items-center justify-between text-white pb-3 px-2" @click.stop>
        <span class="text-sm font-semibold truncate select-text">{{ props.image.title }}</span>
        <div class="flex items-center space-x-2">
          <a
            :href="props.image.url"
            target="_blank"
            class="px-2.5 py-1 rounded-lg bg-[#202737] hover:bg-[#2b3548] text-xs text-sky-400 flex items-center space-x-1"
            title="Open full size / Download"
            @click.stop
          >
            <Download class="w-3.5 h-3.5" />
            <span>Download</span>
          </a>
          <button
            type="button"
            class="p-1.5 rounded-lg bg-black/50 hover:bg-rose-600 text-white transition-colors cursor-pointer"
            @click="emit('close')"
          >
            <X class="w-5 h-5" />
          </button>
        </div>
      </div>

      <div class="max-w-5xl max-h-[85vh] overflow-hidden flex items-center justify-center" @click.stop>
        <img
          :src="props.image.url"
          :alt="props.image.title"
          class="max-w-full max-h-[80vh] object-contain rounded shadow-2xl border border-[#2b3548]"
        />
      </div>
    </div>
  </Teleport>
</template>

